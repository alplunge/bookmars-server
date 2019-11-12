#!/usr/bin/env python3
#
# A *bookmark server* or URI shortener that maintains a mapping (dictionary)
# between short names and long URIs, checking that each new URI added to the
# mapping actually works (i.e. returns a 200 OK).
#
# This server is intended to serve three kinds of requests:
#
#   * A GET request to the / (root) path.  The server returns a form allowing
#     the user to submit a new name/URI pairing.  The form also includes a
#     listing of all the known pairings.
#   * A POST request containing "longuri" and "shortname" fields.  The server
#     checks that the URI is valid (by requesting it), and if so, stores the
#     mapping from shortname to longuri in its dictionary.  The server then
#     redirects back to the root path.
#   * A GET request whose path contains a short name.  The server looks up
#     that short name in its dictionary and redirects to the corresponding
#     long URI.
#
# After writing each step, restart the server and run test.py to test it.

import http.server
import requests
import os
from urllib.parse import unquote, parse_qs
import threading
from socketserver import ThreadingMixIn
from http import cookies
from html import escape as html_escape

memory = {}

form = '''<!DOCTYPE html>
<title>Bookmark Server</title>
<form method="POST">
    <p>
        <label>What's your name again?
            <input type="text" name="yourname">
        </label>
    </p>
    <p>    
        <label>Long URI:
            <input name="longuri">
        </label>
        <br>
        <label>Short name:
            <input name="shortname">
        </label>
        <br>
        <button type="submit">Save it!</button>
    </p>
</form>
<p>URIs I know about:
<pre>
{}
</pre>
'''
class ThreadHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    "This is an HTTPServer that supports thread-based concurrency."

def CheckURI(uri, timeout=5):
    '''Check whether this URI is reachable, i.e. does it return a 200 OK?

    This function returns True if a GET request to uri returns a 200 OK, and
    False if that GET request returns any other response, or doesn't return
    (i.e. times out).
    '''
    # 1. Write this function.  Delete the following line.
    try:
        response = requests.get(uri,timeout=timeout)
        if response.status_code == 200:
            return True
    except requests.RequestException: 
        return False


class Shortener(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # A GET request will either be for / (the root path) or for /some-name.
        # Strip off the / and we have either empty string or a name.
        name = unquote(self.path[1:])

        # Default message if we don't know a name.
        message = "I don't know you yet!"

        # Look for a cookie in the request.
        if 'cookie' in self.headers:
            try:
                # Extract and decode the cookie.
                # Get the cookie from the headers and extract its value
                # into a variable called 'name'.
                c = cookies.SimpleCookie(self.headers["Cookie"])
                name = c["yourname"].value

                # Craft a message, escaping any HTML special chars in name.
                message = "Hey there, " + html_escape(name)
            except (KeyError, cookies.CookieError) as e:
                message = "I'm not sure who you are!"
                print(e)

        if name:
            if name in memory:

                self.send_response(303)
                self.send_header('Location', memory[name])
                self.end_headers()
            else:
                # We don't know that name! Send a 404 error.
                self.send_response(404)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write("I don't know '{}'.".format(name).encode())
        else:
            # Root path. Send the form.
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            # List the known associations and print name from existing cookie in the form.
            known = "\n".join("{} : {}".format(key, memory[key])
                              for key in sorted(memory.keys()))
            finalOutput = known + "\n" + message                 
            self.wfile.write(form.format(finalOutput).encode())

    def do_POST(self):
        # Decode the form data.
        length = int(self.headers.get('Content-length', 0))
        body = self.rfile.read(length).decode()
        params = parse_qs(body)
        yourname = parse_qs(body)["yourname"][0]

        # Create cookie.
        iAmCookie = cookies.SimpleCookie()
        iAmCookie["yourname"] = yourname
        iAmCookie["yourname"]["max-age"] = 600
        iAmCookie["yourname"]["domain"] = 'localhost'

        # Check that the user submitted the form fields.
        if "longuri" not in params or "shortname" not in params:

            self.send_response(400)
            self.send_header('Content-type', 'text/html charset=utf-8')
            self.end_headers()
            self.wfile.write("Missing form fields!".encode())
            return

        longuri = params["longuri"][0]
        shortname = params["shortname"][0]

        if CheckURI(longuri):
            # This URI is good!  Remember it under the specified name.
            memory[shortname] = longuri

            self.send_response(303)
            self.send_header('Location', '/')
            self.send_header('Set-Cookie', iAmCookie['yourname'].OutputString())
            self.end_headers()
        else:
            # Didn't successfully fetch the long URI.
            self.send_response(404)
            self.send_header('Content-type', 'text/html charset=utf-8')
            self.end_headers()
            self.wfile.write("This is unfair!".encode())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000)) 
    server_address = ('', port)
    httpd = ThreadHTTPServer(server_address, Shortener)
    httpd.serve_forever()
