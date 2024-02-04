# start server with python3 sws.py localhost port#
# start client with nc localhost port#

import socket
import select
import queue
import time
import re
import sys
from datetime import datetime
import time

# Check if the correct number of arguments are passed
if len(sys.argv) != 3:
    print("Usage: script.py <host> <port>")
    sys.exit(1)

# Send a 400 Bad Request message
def send_400_bad_request(s):
    if s not in inputs:
        return
    # Respond with 400 Bad Request
    response_messages[s].put('HTTP/1.0 400 Bad Request\n') 
    connection_type[s].put("non-persistent")
    files[s].put('Null\n61038')
    bad_request[s] = True
    send_message(s)

def process_file(s, filename, connection):
    # Load index file if the request is for the root
    if filename == '/':
        filename = '/index.html'
    file_path = f".{filename}"
    file_content = ''

    # Check if the file exists and respond accordingly
    try:
        # Try reading the file and add it to the response message
        with open(file_path, 'r') as file:
            # Add the file contents to the response message             
            file_content = file.read()

        # Respond with 200 OK signaling the file is found
        http_response = ('HTTP/1.0 200 OK\n')

        # Add the response message and file contents
        response_messages[s].put(http_response)
        files[s].put(file_content + '\n61038')
        connection_type[s].put(f"{connection}\n")


    except IOError:
        # Respond with 404 Not Found
        try:
            response_messages[s].put('HTTP/1.0 404 Not Found\n')
            files[s].put('Null\n61038')
            connection_type[s].put(f"{connection}\n")
        except:
            pass

def check_request(s):
     # Check if the request is complete and correct
    request_line = ''.join(list(request_message[s].queue)).replace('\r\n', '\n').lstrip()
    request_lines = request_line.split('\n')
    if not request_line:
        return True

    # Validate the request line
    request = request_lines[0]
    request_regex = r'GET (\/[^ ]*) HTTP\/1\.0'
    request_match = re.match(request_regex, request)
    if not request_match:
        send_400_bad_request(s)
        return False
    return True

def parse_request(s):
    
    # First check for valid request line
    if not check_request(s):
        send_400_bad_request(s)
        return
    
    # Check if the request is complete
    full_request = ''.join(list(request_message[s].queue)).replace('\r\n', '\n')
    if full_request.endswith('\n\n'):
        full_requests = [req for req in full_request.split('\n\n') if req]
        for request in full_requests:
            temp_connection = "non-persistent"

            # Check for correct HTTP header for the connection type
            request_regex = r'GET (\/[^ ]*) HTTP\/1\.0(\n)?([ \t]*[Cc][Oo][Nn][Nn][Ee][Cc][Tt][Ii][Oo][Nn]:[ \t]*(([Kk][Ee][Ee][Pp]-[Aa][Ll][Ii][Vv][Ee])|([Cc][Ll][Oo][Ss][Ee]))[ \t]*)?'
            match = re.search(request_regex, request)
            if match:
                # Check if connection is persistent or non-persistent
                if match.group(4) and match.group(4).strip().lower() == 'keep-alive':
                    temp_connection = "persistent"

            # Process request file
            try:
                filename = match.group(1)
                process_file(s, filename, temp_connection)

            except:
                files[s].put('Null\n61038')
                send_400_bad_request(s)
    
        # Add the connection to the list of outputs because response is ready
        if s not in outputs:
            outputs.append(s)

    else:
        return
    

def send_message(s):
    sending[s] = True
    # Parse the response message
    responses = [res for res in ''.join(list(response_messages[s].queue)).lstrip().split('\n') if res]

    # Parse the requests
    split_requests = [req for req in ''.join(list(request_message[s].queue)).lstrip().split('\n') if req]
    requests = split_requests[0::2]
    
    # Parse the connection type
    connections = [conn for conn in ''.join(list(connection_type[s].queue)).lstrip().split('\n') if conn]

    # Parse the files
    all_files = [file for file in ''.join(list(files[s].queue)).lstrip().split('\n61038') if file]
    
    # Iterate over each request sending the message and printing a log
    for request, response, connection, file in zip(requests, responses, connections, all_files):
        message = ''
        print_connection_type = ''
        if connection == 'persistent':
            print_connection_type = 'Connection: keep-alive'
        else:
            print_connection_type = 'Connection: close'
        if not response == 'HTTP/1.0 400 Bad Request':
            if file == 'Null':
                message = f'{response.rstrip()}\r\n{print_connection_type}\r\n\r\n'
            else:
                message = f'{response.rstrip()}\r\n{print_connection_type}\r\n\r\n{file}'
            s.sendall(message.encode())
        if response == 'HTTP/1.0 400 Bad Request':
            print_connection_type = 'Connection: close'
            message = f'{response.rstrip()}\r\n{print_connection_type}\r\n\r\n'
            s.sendall(message.encode())
        IP, port = s.getpeername()
        
        # Get timezone
        local_time = time.localtime()
        tz_abbr = time.tzname[local_time.tm_isdst]
        # Print the log
        print(datetime.now().strftime(f"%a %b %d %H:%M:%S {tz_abbr} %Y: {IP}:{port} {request}; {response}"))

        # Check if the connection is non-persistent and close the connection
        if connection == 'non-persistent' or response == 'HTTP/1.0 400 Bad Request':
            try:
                del response_messages[s]
                response_messages[s] = queue.Queue()
                del request_message[s]
                request_message[s] = queue.Queue()
                del files[s]
                files[s] = queue.Queue()
            except:
            # Already deleted
                pass
            close_connection(s)
            break
    
    # Remove the messages and files from the queues
    try:
        if s in outputs:
            outputs.remove(s)
        del response_messages[s]
        response_messages[s] = queue.Queue()
        del request_message[s]
        request_message[s] = queue.Queue()
        del files[s]
        files[s] = queue.Queue()
        del connection_type[s]
        connection_type[s] = queue.Queue()
    except:
    # Already deleted
        pass

# Close the connection and remove data of connection
def close_connection(s):
    # Remove data of connection
    for sock in outputs:
        if sock == s:
            outputs.remove(s)
    for sock in inputs:
        if sock == s: 
            inputs.remove(s)
    if s in request_message:
        del request_message[s]
    if s in response_messages:
        del response_messages[s]
    if s in last_activity:
        del last_activity[s]
    if s in connection_type:
        del connection_type[s]
    if s in files:
        del files[s]

    # Close the connection
    s.close()

# Check if the connection has timed out and close if so
def check_timeout(s):
    # Timeout after 30 seconds of inactivity
    try:
        if time.time() - last_activity[s] > 30:
            close_connection(s)
            return True
    except KeyError:
        # No activity logged for this socket
        return False
    return False


# Create a TCP/IP socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Re-use the socket
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Non-blocking mode
server.setblocking(0)

# Bind the socket to the port
server.bind((sys.argv[1], int(sys.argv[2])))

# Listen for incoming connections
server.listen(5)

# Sockets from which we expect to read
inputs = [server]

# Sockets from which we expect to write
outputs = []

# Outgoing message queues (socket:Queue)
response_messages = {}

# Incoming message queues (socket:Queue)
request_message = {}

# Record the last activity time for each socket
last_activity = {}

# Record the connection type for each socket
connection_type = {}

# Files to be sent
files = {}

# Messages sending
sending = {}

# Bad requests
bad_request = {}


# Continuously process connection inputs and outputs
while True:
    # Wait for at least one of the sockets to be ready for processing
    try:
        readable, writable, exception = select.select(inputs, outputs, inputs, 0.1)
    except ValueError:
        close_connection(outputs[0])
        readable, writable, exception = select.select(inputs, outputs, inputs, 0.1)
    
    # Handle inputs
    for s in readable:
        # Server socket is ready to accept a new connection
        if s is server:
            # A "readable" server socket is ready to accept a connection
            connection, client_address = s.accept()

            # Record the last activity time of the socket
            last_activity[connection] = time.time()

            # Make the connection non-blocking
            connection.setblocking(0)

            # Add the connection to the list of inputs
            inputs.append(connection)

            # Create a queue for incoming messages on this connection
            request_message[connection] = queue.Queue()

            # Create a queue for outgoing messages on this connection
            response_messages[connection] = queue.Queue()

            # Create a queue for files to be sent on this connection]
            files[connection] = queue.Queue()

            # Create a queue for the connection type
            connection_type[connection] = queue.Queue()
            
            # Create a boolean for the sending status
            sending[connection] = False

            

        # Client socket is ready to read
        else:
            # Read client data
            data = s.recv(1024).decode()
            if data:
                # Update the last activity time
                last_activity[s] = time.time()

                # Add client data to the queue
                request_message[s].put(data)

                # Parse the request
                parse_request(s)

                

    
    # Handle outputs
    for s in writable:
        # A writeable server socket has a message for the client
        # Send the response message
        if not sending[s]:
            send_message(s)
    
    # Handle exceptions
    for s in exception: 
        # Stop listening for input on the connection
        close_connection(s)
    
    # Handle timeouts
    for s in list(inputs):
        check_timeout(s)






