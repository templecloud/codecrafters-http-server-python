import socket


def main():
    print(f'Starting Server...')

    # Open a TCP socket on localhost:4221 and wait for client connections
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    print(f'Server is listening on {server_socket.getsockname()}...')

    while True:
        # 1. Accept the client connection.
        client_socket, client_address = server_socket.accept()
        print(f'Accepted connection from {client_address}')

        # 2. Prepare the client response.
        response = b'HTTP/1.1 200 OK\r\n\r\n'

        # 3. Send the response to the client.
        client_socket.sendall(response)

        # 4. Gracefully shutdown and close the connection.
        client_socket.shutdown(socket.SHUT_RDWR)
        client_socket.close()


if __name__ == "__main__":
    main()
