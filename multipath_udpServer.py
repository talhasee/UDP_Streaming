import cv2
import numpy as np
import socket
import time
import threading
import base64
import sys


BUFF_SIZE = 1500
NUM_PACKETS = 10
PATH = "1" #chosen path

count = 0
TERMINATE = False
path1_rtt = []
path2_rtt = []

def decidePath(Path1, Path2):
    global count, TERMINATE, PATH
    time_interval = 3
    while not TERMINATE:
        time.sleep(time_interval)
        for _ in range(NUM_PACKETS):
            start_time = time.time()
            mssg = "Ping Path1"
            tcpPath1Sock.sendall(mssg.encode())
            data = tcpPath1Sock.recv(BUFF_SIZE)
            end_time = time.time()
            rtt = (end_time - start_time)
            path1_rtt.append(rtt)
            # print(f"Received echo on port {Path1[1]}: {data.decode()} | RTT: {rtt:.2f} ms")

            start_time = time.time()
            mssg = "Ping Path2"
            tcpPath2Sock.sendall(mssg.encode())
            data = tcpPath2Sock.recv(BUFF_SIZE)
            end_time = time.time()
            rtt = (end_time - start_time) 
            path2_rtt.append(rtt)
            # print(f"Received echo on port {Path2[1]}: {data.decode()} | RTT: {rtt:.2f} ms")

        medianPath1 = np.median(path1_rtt)
        medianPath2 = np.median(path2_rtt)
        # print(path1_rtt, path2_rtt)
        if medianPath1 > medianPath2:
            print(path1_rtt)
            print(f"Median after {count} frames - Path1 - {medianPath1} ms, Path2 - {medianPath2} ms")
            PATH = "2"
        elif medianPath1 < medianPath2:
            print(path2_rtt)
            print(f"Median after {count} frames - Path1 - {medianPath1} ms, Path2 - {medianPath2} ms")
            PATH = "1"

        path1_rtt.clear()
        path2_rtt.clear()

        

# Method responsible ffor handling the client_connection.
def handle_client(addr, addr1, tcp_Addr):
    # print('Client connected from:', addr)
    global count, TERMINATE
    fps, st, frames_cnt = (0, 0, 20)
    display = 0
    change = 1
    vid = cv2.VideoCapture("Short.mp4")

    path1Packets = 0
    path2Packets = 0
    while vid.isOpened(): 

        ret, frame = vid.read()
        
        if not ret:
            # If the video is finished, break out of the loop
            break

        # Check if the frame is empty (which can happen if the camera is not working)
        if frame is None:
            print("Empty frame")
            continue
        #do we have to change the socket or not
        if PATH == 1:
            change = 1
        elif PATH == 2:
            change == 2

        # Encoding the frame and obtaining a buffer out of it. (buffer contains byte-array -> pixel values)
        encoded, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        # Calculate the size of the frame buffer.
        frame_size = len(buffer)
        timestamp = "{:.4f}".format(time.time())

        # Convert the frame size to a string and prefix it with a delimiter (e.g., '|')

        if(change == 1):
            frame_size_str = "|1" + timestamp + str(frame_size)
        elif change == 2:
            frame_size_str = "|2" + timestamp + str(frame_size)

        # Updating the frame_displayed_count.
        display += 1
        # print("Sent packet num - ", display," with size - ", frame_size_str)

        #Send the frame size to the client before sending the frame data (Sending via TCP socket)
        tcp_Socket.send(frame_size_str.encode())
        
        # Splitting the frame_buffer into smaller chunks (of size chunk_size)
        chunk_size = 1500
        # Initializing a variable to track number of chunks sent for the current frame.
        chunks = 0

        # Iterating the buffer and sending each chunk one after another.
        for i in range(0, len(buffer), chunk_size):
            chunks += 1
            chunk = buffer[i:i + chunk_size]
            encoded_chunk = base64.b64encode(chunk)
            if(change == 1):
                server_socket.sendto(encoded_chunk, addr)
                path1Packets += 1
            elif change == 2:
                server_socket2.sendto(encoded_chunk, addr1)
                path2Packets += 1

        # Displaying the frame statistics at server side (for debugging purpose).
        # print("Frame -Time ", timestamp, "FRAME NUM - ", display ," ", frame_size, " SENT chunks - ", chunks)
        
        # Adding fps statistics in addition to the frame being sent.
        frame = cv2.putText(frame, 'FPS: ' + str(fps), (10, 40), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 255), 2)

        # Displaying the frame sent at server-side.
        cv2.imshow('Server Video', frame)

        key = cv2.waitKey(1)  # Update the display
        if key == ord('q'):
            server_socket.close()
            server_socket2.close()
            tcp_Socket.close()
            TERMINATE = True
            break

        if count == frames_cnt:
            try:
                fps = round(frames_cnt / (time.time() - st))
                st = time.time()
                count = 0
            except:
                pass
        count += 1

    cv2.destroyAllWindows()
    vid.release()
    
    # Sending end-frame to let the client know about it.
    end_string = "@" + str(display-1)
    print("Last frame data - ", end_string)
    server_socket.sendto(end_string.encode(), addr)
    server_socket2.sendto(end_string.encode(), addr1)

    # Logging connection termination event at server-side.
    server_socket.close()
    server_socket2.close()

    tcp_Server_Socket.close()

    TERMINATE = True

    print('Successfully terminated connection with the client:', addr)

    print("Packets Sent on Path 1:", path1Packets)
    print("Packets Sent on Path 2:", path2Packets)

def get_ip_address():
    try:
        # Create a temporary socket to get the IP address
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))  # Connecting to a known external server
        ip_address = sock.getsockname()[0]
        sock.close()
        return ip_address
    except socket.error as e:
        print("Error occurred:", e)
        return None

# Creating the server socket (UDP)
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_socket2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Creating the server socket (TCP)
tcp_Server_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
server_socket2.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)

host_name = socket.gethostname()

host_ip = get_ip_address()
if host_ip:
    print("IP Address: ", host_ip)
else:
    print("Failed to obtain IP Address. Exiting the code")
    sys.exit(1)

port = 12345
port1 = 12347
tcp_port = 12346
host_ip2 = "192.168.29.98"
socket_address = (host_ip, port)
socket_address2 = (host_ip2, port1)

tcp_Socket_Address = (host_ip, tcp_port)

#Binding the TCP socket
tcp_Server_Socket.bind(tcp_Socket_Address)

#TCP Socket Listening
tcp_Server_Socket.listen(5)

# Bind the socket to the address (UDP)
server_socket.bind(socket_address)

server_socket2.bind(socket_address2)

# Accept a client connection --> Blocking Call
data, addr = server_socket.recvfrom(1024)
print('Connection from: (UDP)', addr)
# print(data)


data1, addr1 = server_socket2.recvfrom(1024)
print('Connection from: (UDP)', addr1)

tcp_Socket, tcp_Addr = tcp_Server_Socket.accept()
print("Connection from: (TCP)", tcp_Addr)


#***************Sockets for RTT calculation communication*****************
tcpPath1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcpPath2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


tcpPath1.bind((host_ip, 11111))
tcpPath2.bind((host_ip2, 11111))

tcpPath1.listen(5)
tcpPath2.listen(5)

tcpPath1Sock, addrPath1 = tcpPath1.accept()
print("Connection Established for RTT calc. PATH1 - ", addrPath1)

tcpPath2Sock, addrPath2 = tcpPath2.accept()
print("Connection Established for RTT calc. PATH2 - ", addrPath2)

#Sample mssges
# tcpPath1.sendall("Testing Path1".encode())
# tcpPath2.sendall("Testing Path2".encode())

time_interval = 4
rttThread = threading.Thread(target = decidePath, args=(addrPath1, addrPath2))
rttThread.start()


# Create a new thread to handle the client
client_thread = threading.Thread(target=handle_client, args=(addr, addr1, tcp_Addr))
client_thread.start()