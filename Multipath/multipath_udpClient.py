import cv2
import socket
import numpy as np
import time
import base64
import threading
import queue
import sys
import matplotlib.pyplot as plt

BUFFER_SIZE = 2000  

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

# Define server's address for path 1 
server_ip = get_ip_address()
 
# Or insert IP below manually
# server_ip = "IP Address"

if server_ip:
    print("IP Address:", server_ip)
else:
    print("Failed to obtain IP address. Exiting the script.")
    sys.exit(1)

#************Path 1****************

# Creating a socket for client (UDP socket - PATH 1)
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_port = 12345 #path1
server_addr_port = (server_ip, server_port)

# Initiating the connection with server_socket using UDP
client_socket.sendto("Initial Message".encode(), server_addr_port)



#************Path 2****************

# Creating a socket for client (UDP socket - PATH 2)
client_socket2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_port1 = 12347 #path2

#Change IP Address for Path2
server_ip2 = "192.168.45.244"

server_addr_port1 = (server_ip2, server_port1)

bytes = client_socket2.sendto("Initial Message".encode(), server_addr_port1)


#*********Path for Control Frame**********

# Creating a socket for client (TCP socket)
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_server_port = 12346
tcp_server_addr_port = (server_ip, tcp_server_port)

# Connect to the TCP server
tcp_socket.connect(tcp_server_addr_port)
print("Connected to TCP SERVER:", tcp_server_addr_port)


#***************************Sockets for RTT calculation communication******************

#Sockets for minRTT calculating
tcpPath1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcpPath2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

tcpPath1.connect((server_ip, 11111))

tcpPath2.connect((server_ip2, 11111))


#*************Useful variables**************

frame_data = b""  #frame data for chunks summation
expected_frame_size = 0 #Frame size expected by UDP conn. of incoming frame
frames_displayed = 0 #How many frames displayed
frames_sent = 0 #Number of frames received

fps, st, frame_cnt, count = (0, 0, 20, 0) #Helper variables
displays = 0
chunks = 0
num = 0
timestamp = "" #timestamp of current frame

latency_list = [0] #list for storing latency of current frame received w.r.t previous frame

path1Packets = 0
path2Packets = 0

# Create a queue for frame data
frame_queue = queue.Queue()

#Needs to be completed for RTT communication

def rttCommunication():
    while(1):
        packet = tcpPath1.recv(BUFFER_SIZE)
        mssg = "PingP1"
        tcpPath1.send(mssg.encode())
        packet = tcpPath2.recv(BUFFER_SIZE)
        mssg = "PingP2"
        tcpPath2.send(mssg.encode())

# Thread for handeling minRTT calculation
rttCalcThread = threading.Thread(target=rttCommunication)
rttCalcThread.start()

'''
In this function a TCP socket will be receiving the packet that include frame_size for incoming frame 
and also same packet includes timestamp as well as which path udp socket will be chosing

Format of packet

|17894561230.123465464
^^^             ^
|||_____________|-->timestamp(size of timestamp will be same everytime)
||
||____Path which UDP will follow
|
|
|
Delimiter


Lastly, everything followed by timestamp is Frame Size
'''
def receive_frame_size():
    global expected_frame_size, latency_list, frames_sent, temp
    frame_info = b""  # Initialize an empty buffer to store received data

    while True:
        packet = tcp_socket.recv(2000)  # Adjust buffer size if needed
        frame_info += packet  # Append the received packet to the buffer

        # Split the buffer by the delimiter "|"
        frame_info_parts = frame_info.split(b'|')

        # Process complete frame size info
        if len(frame_info_parts) > 1:

            timestamp = (float)(packet[2:17].decode())
            idx = len(latency_list) - 1
            val = (int)((time.time() - latency_list[idx])*1000)
            # print("LATENCY:",val)
            latency_list[idx] = val
            latency_list.append(timestamp)
            expected_frame_size = int(frame_info_parts[1][16:].decode())
            # Remove the processed part from the buffer
            frame_info = b"".join(frame_info_parts[2:])

        if not packet:
            break

# Thread to handle the reception of the control frame
receive_frame_size_thread = threading.Thread(target=receive_frame_size)
receive_frame_size_thread.start()

# Function to process frames
def process_frames():
    global fps, st, count, frames_displayed
    while True:
        if not frame_queue.empty():
            complete_frame_data = frame_queue.get()
            try:
                frame = cv2.imdecode(np.frombuffer(complete_frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
            except cv2.error as e:
                print(f"Error decoding frame: {e}")
                continue
            
            if frame is not None:
                frame = cv2.putText(frame, 'FPS: ' + str(fps), (10, 40), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 255), 2)
                frames_displayed += 1
                cv2.imshow("RECEIVING AT CLIENT", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            cv2.destroyAllWindows()
            client_socket.close()
            client_socket2.close()
            tcp_socket.close()
            break

# Function to receive data (in form of chunks) and manage frames after it is generated
def receive_data_path1():
    global frame_data, displays, fps, st, count, chunks, num, timestamp, frames_sent, path1Packets, path2Packets
    while True:
        packet = None

        packet, ret = client_socket.recvfrom(BUFFER_SIZE)
        path1Packets += 1

        # Checking for ending-frame:
        if(packet.startswith(b'@')):
            frames_sent = (int)(packet.decode().split('@')[1])
            print("Received All Video Frames - ", frames_sent)

            # Plotting Network Latency
            latency_list.pop(0)
            x =  [i for i in range(1, len(latency_list) + 1)]
            plt.switch_backend('Agg')  
            plt.figure(figsize=(20, 10))
            plt.scatter(x, latency_list)
            plt.xlabel('Frame Number')
            plt.ylabel('Network Latency (in milliseconds)')
            plt.savefig('plot.png')
            
            break
        else:
            data = base64.b64decode(packet)
            frame_data += data
            chunks += 1
        
        if len(frame_data) >= expected_frame_size:
            displays += 1
            # print("Time - ", timestamp, "Curr-Time ", str(time.time()),"Frame NUM - ", displays, " chunks - ", chunks, " expec_frame_size - ", expected_frame_size, " frame_data - ", len(frame_data))
            if count == frame_cnt:
                try:
                    fps = round(frame_cnt / (time.time() - st))
                    st = time.time()
                    count = 0
                except:
                    pass
            count += 1
            frame_queue.put(frame_data)
            frame_data = b""


def receive_data_path2():
    global frame_data, displays, fps, st, count, chunks, num, timestamp, frames_sent, path1Packets, path2Packets
    while True:
        packet = None

        packet, ret = client_socket2.recvfrom(BUFFER_SIZE)
        path2Packets += 1

        # Checking for ending-frame:
        if(packet.startswith(b'@')):
            '''
            Graph is being calculated in Path 1 code
            '''
            break
        else:
            data = base64.b64decode(packet)
            frame_data += data
            chunks += 1
        
        if len(frame_data) >= expected_frame_size:
            displays += 1
            # print("Time - ", timestamp, "Curr-Time ", str(time.time()),"Frame NUM - ", displays, " chunks - ", chunks, " expec_frame_size - ", expected_frame_size, " frame_data - ", len(frame_data))
            if count == frame_cnt:
                try:
                    fps = round(frame_cnt / (time.time() - st))
                    st = time.time()
                    count = 0
                except:
                    pass
            count += 1
            frame_queue.put(frame_data)
            frame_data = b""


# Create a thread for receiving data.
receive_thread = threading.Thread(target=receive_data_path1)
receive_thread.start()

receive_thread2 = threading.Thread(target=receive_data_path2)
receive_thread2.start()

# Running processing_frames() on main thread.
process_frames()

# Waiting for the main receive_thread to finish and then close the socket.
receive_thread.join()


# Close the client socket when done.
client_socket.close()
client_socket2.close()
tcp_socket.close()


# cv2.destroyAllWindows()
print("Frames sent - ", frames_sent, " Frames displayed - ", frames_displayed)
packet_loss = max(0, (frames_sent - frames_displayed)*100/(frames_sent))
print("VIDEO FRAMES LOSS:", round(packet_loss,4), end =" %\n")
print("AVERAGE LATENCY:", sum(latency_list)/len(latency_list))
print("Successfully Terminated Client Program.")

print("Packets received on Path 1:", path1Packets)
print(" Packets received on Path 2:", path2Packets)