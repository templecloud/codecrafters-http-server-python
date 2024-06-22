import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import gzip
import io
import socket
import threading
import traceback

# Manual Curl Tests -------------------------------------------------------------------------------
# 

# curl -v http://localhost:4221 ;echo
# curl -v http://localhost:4221/unknown ;echo
# curl -v http://localhost:4221/echo/Hello ;echo
# curl -v http://localhost:4221/echo -d 'Hello' ;echo
# curl -v --header "User-Agent: foobar/1.2.3" http://localhost:4221/user-agent ;echo
# curl -i -X POST http://localhost:4221/files/foo -d 'Hello, World!' ;echo
# curl -i http://localhost:4221/files/foo ;echo
# curl -i http://localhost:4221/files/non_existant_file :echo
# curl -v --data "12345" -H "Content-Type: application/octet-stream" http://localhost:4221/files/file_123 :echo
# curl -v -H "Accept-Encoding: gzip" http://localhost:4221/echo/abc | hexdump -C


# Classes -----------------------------------------------------------------------------------------
# 

CLRF = "\r\n"

class HttpRequest:
    def __init__(self, request_data):
        request_lines = request_data.split(CLRF)
        current_line = 1

        self.request_data = request_data
        self.verb, self.path, self.protocol = request_lines[0].split(' ')
        self.headers = {}
        # Extract headers (if present)
        for line in request_lines[1:]:
            if not line:
                break
            key, value = line.split(':', 1)
            self.headers[key.strip()] = value.strip()
            current_line += 1

        self.request_body = []
        # Extract body (if present)
        self.request_body = request_lines[current_line+1:][0]

    def get_header(self, key):
        return self.headers.get(key)

    def get_body(self):
        return self.request_body

    def get_path(self):
        return self.path

    def get_verb(self):
        return self.verb

    def get_protocol(self):
        return self.protocol

    def get_request_data(self):
        return self.request_data

    def __str__(self):
        return f"Request Line: {self.request_line}, Headers: {self.headers}, Request Body: {self.request_body}"

class HttpResponse:
    def __init__(self, http_request: HttpRequest):
        self.http_request = http_request
        
        self.protocol = http_request.get_protocol()
        self.status_code = 0
        self.reason = None

        self.headers = {}
        self.headers['Content-Length'] = 0

        self.body = None
        self.encoding = 'utf-8'
        self.compressed = False
    
    def with_status(self, status_code, reason) -> 'HttpResponse':
        self.status_code = status_code
        self.reason = reason
        return self

    def with_body(self, body, content_type: str=None) -> 'HttpResponse':
        self.body = body
        self.headers['Content-Length'] = len(body)
        if content_type:
            self.headers['Content-Type'] = content_type
        return self

    def as_http_response_bytes(self) -> bytes:
        body_bytes: bytes = b''
        if self.body:
            if self.encoding == 'gzip':
                self.with_body(gzip_string(self.body), content_type='text/plain')
                self.headers['Content-Encoding'] = 'gzip'
                body_bytes = self.body
            else:
                body_bytes = self.body.encode(self.encoding)

        headers_bytes: bytes = b''
        for key, value in self.headers.items():
            headers_bytes += (f'{key}: {value}' + CLRF).encode('utf-8')
        headers_bytes += CLRF.encode('utf-8')

        status_bytes: bytes = (f'{self.protocol} {self.status_code} {self.reason}' + CLRF).encode('utf-8')

        return status_bytes + headers_bytes + body_bytes

class HttpContext:
    def __init__(self):
        self.directory = None

    def with_directory(self, directory):
        self.directory = directory
        return self


# Support Functions -------------------------------------------------------------------------------
# 

def encode_bytes_to_base64(byte_data):
    # Encode bytes to Base64 string
    base64_str = base64.b64encode(byte_data).decode('utf-8')
    return base64_str


def decode_base64_to_bytes(base64_str):
    # Decode Base64 string back to bytes
    byte_data = base64.b64decode(base64_str.encode('utf-8'))
    return byte_data


def gzip_string(input_string) -> bytes:
    # Create a BytesIO buffer to hold the compressed data
    mem_buf = io.BytesIO()
    
    # Use the gzip module to write the compressed data to the buffer
    with gzip.GzipFile(fileobj=mem_buf, mode='wb') as f:
        f.write(input_string.encode('utf-8'))
    
    # Get the compressed data from the buffer
    return mem_buf.getvalue()


# HTTP WebServer Functions ------------------------------------------------------------------------
# 

def handle_request(context: HttpContext, request: HttpRequest) -> HttpResponse:
    path = request.get_path()
    response : HttpResponse = None
    # Prepare the client response.
    if path == '/':
        # curl -v http://localhost:4221; echo
        response = HttpResponse(request).with_status(200, 'OK')
    elif path.startswith('/echo'):
        echo_path_args = path.replace('/echo', '', 1)
        if (len(echo_path_args) > 1):
            # curl -v http://localhost:4221/echo/Hello; echo
            rs_body = echo_path_args[1:]
            response = HttpResponse(request).with_status(200, 'OK')\
                .with_body(rs_body, content_type='text/plain')
        elif (len(request.get_body()) > 1):
            # curl -v http://localhost:4221/echo -d 'Hello'; echo
            rs_body = request.get_body() 
            response = HttpResponse(request).with_status(200, 'OK')\
                .with_body(rs_body, content_type='text/plain')
        else:
            response = HttpResponse(request).with_status(200, 'OK')
    elif path.startswith('/user-agent'):
        # curl -v --header "User-Agent: foobar/1.2.3" http://localhost:4221/user-agent; echo
        rs_body = request.get_header('User-Agent')
        response =  HttpResponse(request).with_status(200, 'OK')\
            .with_body(rs_body, content_type='text/plain')
    elif request.get_verb() == 'GET' and path.startswith('/files'):
        path_parts = path.split('/')
        if len(path_parts) == 3:
            file_path = path_parts[2]
            try:
                # echo -n 'Hello, World!' > /tmp/foo
                # curl -i http://localhost:4221/files/foo
                with open(f'{context.directory}/{file_path}', 'r') as file:
                    body = file.read()
                    response = HttpResponse(request).with_status(200, 'OK')\
                        .with_body(body, content_type='application/octet-stream')
            except FileNotFoundError:
                # curl -i http://localhost:4221/files/non_existant_file
                response = HttpResponse(request).with_status(404, 'Not Found')
            except Exception as e:
                print(f"Error reading file: {e}")
                traceback.print_exc()
                response = HttpResponse(request).with_status(500, 'Internal Server Error')
        else:
            response = HttpResponse(request).with_status(404, 'Not Found')
    elif request.get_verb() == 'POST' and path.startswith('/files'):
        path_parts = path.split('/')
        if len(path_parts) == 3:
            file_path = path_parts[2]
            try:
                # curl -i -X POST http://localhost:4221/files/foo -d 'Hello, World!'
                # curl -v --data "12345" -H "Content-Type: application/octet-stream" http://localhost:4221/files/file_123
                with open(f'{context.directory}/{file_path}', 'w') as file:
                    file.write(request.get_body())
                    response = HttpResponse(request).with_status(201, 'Created')
            except Exception as e:
                print(f"Error writing file: {e}")
                traceback.print_exc()
                response = HttpResponse(request).with_status(500, 'Internal Server Error')
    else:
        # curl -v http://localhost:4221/unknown; echo
        response = HttpResponse(request).with_status(404, 'Not Found')

    return response


def handle_response(context: HttpContext, response: HttpResponse) -> HttpResponse:
    encodings = response.http_request.get_header('Accept-Encoding')
    encoding_list = encodings.split(',') if encodings else []
    for encoding in encoding_list:
        if encoding and encoding.strip().lower() == 'gzip':
            # curl -v -H "Accept-Encoding: gzip" http://localhost:4221/echo/abc | hexdump -C
            # Compress the response body using gzip encoding
            response.encoding = 'gzip'
    return response


def handle_client(context: HttpContext, client_socket, client_address):
    print(f'Accepted connection from {client_address}')
    try:
        # Receive the request data from the client.
        # TODO: Handle large requests that require multiple recv calls.
        request_data = client_socket.recv(1024).decode('utf-8')

        request = HttpRequest(request_data)
        response = handle_request(context, request)
        response = handle_response(context, response)

        # Send the response to the client.
        client_socket.sendall(response.as_http_response_bytes())
    except Exception as e:
        print(f"Error handling client {client_address}: {e}")
        traceback.print_exc()
    finally:
        # Gracefully shutdown and close the connection.
        client_socket.shutdown(socket.SHUT_RDWR)
        client_socket.close()


def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Simple HTTP Server')
    parser.add_argument('--directory', type=str, help='Directory to serve', default='/tmp')
    parser.add_argument('--port', type=int, help='Port to listen on', default=4221)
    parser.add_argument('--mode', type=str, help='Threading mode', default='pooled')
    args = parser.parse_args()

    # Dertermine with to use thread pool mode or spawn a new thread for each client connection.
    # NB: TODO: Add an async mode using asyncio.
    thread_pool_mode = True if args.mode == 'pooled' else False
    directory = args.directory
    port = args.port    

    print(f'Starting Server on port {port}...')
    print(f'Thread Pool Mode: {thread_pool_mode}')

    context = HttpContext().with_directory(directory)

    # Open a TCP socket on localhost:4221 and wait for client connections
    server_socket = socket.create_server(("localhost", port), reuse_port=True)
    print(f'Server is listening on {server_socket.getsockname()}...')

    if thread_pool_mode:
        # Create a ThreadPoolExecutor to manage a pool of threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            while True:
                # Accept the client connection.
                client_socket, client_address = server_socket.accept()
                
                # Submit the client handling function to the thread pool
                executor.submit(handle_client, context, client_socket, client_address)
    else:
        while True:
            # Accept the client connection.
            client_socket, client_address = server_socket.accept()

            # Start a new thread to handle the client connection
            client_handler = threading.Thread(
                target=handle_client,
                args=(context, client_socket, client_address)
            )
            client_handler.start()

if __name__ == "__main__":
    main()
