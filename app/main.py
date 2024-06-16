import socket

def main():
    print(f'Starting Server...')

    # Open a TCP socket on localhost:4221 and wait for client connections
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    print(f'Server is listening on {server_socket.getsockname()}...')

    CLRF = "\r\n"

    while True:
        # Accept the client connection.
        client_socket, client_address = server_socket.accept()
        print(f'Accepted connection from {client_address}')

        # Receive the request data from the client.
        request_data = client_socket.recv(1024).decode('utf-8')

        # Split request data into lines
        request_lines = request_data.split(CLRF)
        
        # Extract and print the request line
        request_line = request_lines[0]
        print(f"Request Line: {request_line}")
        verb, path, protocol = request_line.split(' ')
        print(f'Verb: {verb}., path: {path}, protocol: {protocol}')

        # Initialize headers dictionary
        headers = {}
        current_line = 1
        # Parse Headers
        for line in request_lines[1:]:
            if not line:
                break
            key, value = line.split(':', 1)
            headers[key.strip()] = value.strip()
            print(f'Header: {key} = {value}')
            current_line += 1

        # Extract and print the request body (if present)
        request_body = request_lines[current_line+1:]
        print(f"Request Body: {request_body}")

        # Prepare the client response.
        if path == '/':
            # curl -v http://localhost:4221
            response = (f'HTTP/1.1 200 OK' + CLRF + CLRF).encode('utf-8')
        elif path.startswith('/echo'):
            # curl -v http://localhost:4221/echo/Hello; echo
            echo_path_args = path.replace('/echo', '', 1)
            print(f'Echo Path Args: {echo_path_args}')
            if (len(echo_path_args) > 1):
                echo_path_args = echo_path_args[1:]
                print(f'Request Url Path...')
                response_status = f'HTTP/1.1 200 OK'
                content_type_header = f'Content-Type: text/plain'
                content_length_header = f'Content-Length: {len(echo_path_args)}'
                body = echo_path_args
                response = (
                    response_status + CLRF
                    + content_type_header + CLRF + content_length_header + CLRF + CLRF 
                    + (body + CLRF if body else '')
                    ).encode('utf-8')
            elif (len(request_body[0]) > 1):
                 # curl -v http://localhost:4221/echo -d 'Hello'; echo
                response_status = f'HTTP/1.1 200 OK'
                content_type_header = f'Content-Type: text/plain'
                content_length_header = f'Content-Length: {len(request_body[0])}'
                body = request_body[0]
                response = (
                    response_status + CLRF
                    + content_type_header + CLRF + content_length_header + CLRF + CLRF 
                    + (body + CLRF if body else '')
                    ).encode('utf-8')
            else:
                response_status = f'HTTP/1.1 200 OK'
                response = (
                    response_status + CLRF
                ).encode('utf-8')
            
            print(f'Response: {response}')
        else:
            # curl -v http://localhost:4221/unknown
            response = (f'HTTP/1.1 404 Not Found' + CLRF +CLRF).encode('utf-8')

        # Send the response to the client.
        client_socket.sendall(response)

        # Gracefully shutdown and close the connection.
        client_socket.shutdown(socket.SHUT_RDWR)
        client_socket.close()


if __name__ == "__main__":
    main()
