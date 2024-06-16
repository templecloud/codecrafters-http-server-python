import socket

def main():
    print(f'Starting Server...')

    # Open a TCP socket on localhost:4221 and wait for client connections
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    print(f'Server is listening on {server_socket.getsockname()}...')

    while True:
        # Accept the client connection.
        client_socket, client_address = server_socket.accept()
        print(f'Accepted connection from {client_address}')

        # Receive the request data from the client.
        request_data = client_socket.recv(1024).decode('utf-8')

        # Split request data into lines
        LINE_DELIMITER = "\r\n"
        request_lines = request_data.split(LINE_DELIMITER)
        
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
            response = b'HTTP/1.1 200 OK\r\n\r\n'
        else:
            response = b'HTTP/1.1 404 Not Found\r\n\r\n'

        # Send the response to the client.
        client_socket.sendall(response)

        # Gracefully shutdown and close the connection.
        client_socket.shutdown(socket.SHUT_RDWR)
        client_socket.close()


if __name__ == "__main__":
    main()
