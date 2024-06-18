import socket
import threading
from concurrent.futures import ThreadPoolExecutor

CLRF = "\r\n"

class HTTPRequest:
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

class HTTPResponse:
    def __init__(self, rq: HTTPRequest):
        self.rq = rq
        
        self.protocol = rq.get_protocol()
        self.status_code = 0
        self.reason = None

        self.headers = {}
        self.headers['Content-Length'] = 0

        self.body = None
        self.encoding = 'utf-8'
    
    def with_status(self, status_code, reason) -> 'HTTPResponse':
        self.status_code = status_code
        self.reason = reason
        return self

    def with_body(self, body: str, encoding="utf-8", content_type: str=None) -> 'HTTPResponse':
        self.body = body
        self.encoding = encoding
        self.headers['Content-Length'] = len(body)
        if content_type:
            self.headers['Content-Type'] = content_type
        return self

    def as_http_response(self) -> str:
        response = f'{self.protocol} {self.status_code} {self.reason}' + CLRF
        for key, value in self.headers.items():
            response += f'{key}: {value}' + CLRF
        response += CLRF
        response += self.body if self.body else ''
        return response

    def as_http_response_bytes(self) -> bytes:
        return self.as_http_response().encode(self.encoding)
    

def handle_request(request: HTTPRequest) -> HTTPResponse:
    path = request.get_path()
    response : HTTPResponse = None
    # Prepare the client response.
    if path == '/':
        # curl -v http://localhost:4221; echo
        response = HTTPResponse(request).with_status(200, 'OK')
    elif path.startswith('/echo'):
        echo_path_args = path.replace('/echo', '', 1)
        if (len(echo_path_args) > 1):
            # curl -v http://localhost:4221/echo/Hello; echo
            rs_body = echo_path_args[1:]
            response = HTTPResponse(request).with_status(200, 'OK')\
                .with_body(rs_body, content_type='text/plain')
        elif (len(request.get_body()) > 1):
            # curl -v http://localhost:4221/echo -d 'Hello'; echo
            rs_body = request.get_body() 
            response = HTTPResponse(request).with_status(200, 'OK')\
                .with_body(rs_body, content_type='text/plain')
        else:
            response = HTTPResponse(request).with_status(200, 'OK')
    elif path.startswith('/user-agent'):
        # url -v --header "User-Agent: foobar/1.2.3" http://localhost:4221/user-agent; echo
        rs_body = request.get_header('User-Agent')
        response =  HTTPResponse(request).with_status(200, 'OK')\
            .with_body(rs_body, content_type='text/plain')
    else:
        # curl -v http://localhost:4221/unknown; echo
        response = HTTPResponse(request).with_status(404, 'Not Found')

    return response

def handle_client(client_socket, client_address):
    print(f'Accepted connection from {client_address}')
    try:
        # # Receive the request data from the client.
        request_data = client_socket.recv(1024).decode('utf-8')

        request = HTTPRequest(request_data)
        response = handle_request(request)

        # Send the response to the client.
        client_socket.sendall(response.as_http_response_bytes())

    finally:
        # Gracefully shutdown and close the connection.
        client_socket.shutdown(socket.SHUT_RDWR)
        client_socket.close()


def main():
    # Dertermine with to use thread pool mode or spawn a new thread for each client connection.
    # NB: TODO: Add an async mode using asyncio.
    thread_pool_mode = True

    print(f'Starting Server.. ')
    print(f'Thread Pool Mode: {thread_pool_mode}')

    # Open a TCP socket on localhost:4221 and wait for client connections
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    print(f'Server is listening on {server_socket.getsockname()}...')

    if thread_pool_mode:
        while True:
            # Accept the client connection.
            client_socket, client_address = server_socket.accept()

            # Start a new thread to handle the client connection
            client_handler = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address)
            )
            client_handler.start()
    else:
        # Create a ThreadPoolExecutor to manage a pool of threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            while True:
                # Accept the client connection.
                client_socket, client_address = server_socket.accept()
                
                # Submit the client handling function to the thread pool
                executor.submit(handle_client, client_socket, client_address)


if __name__ == "__main__":
    main()
