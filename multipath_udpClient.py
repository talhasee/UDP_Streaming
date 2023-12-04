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

if server_ip:
    print("IP Address:", server_ip)
else:
    print("Failed to obtain IP address. Exiting the script.")
    sys.exit(1)


#************Path 1****************
# Creating a socket for client (UDP socket)
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_port = 12345 #path1
server_addr_port = (server_ip, server_port)

# Initiating the connection with server_socket using UDP
client_socket.sendto("Initial Message".encode(), server_addr_port)

#************Path 2****************
client_socket2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_port1 = 12347 #path2
server_ip2 = "192.168.29.98"

server_addr_port1 = (server_ip2, server_port1)

bytes = client_socket2.sendto("Initial Message".encode(), server_addr_port1)


#*********Helper Path**********
# Creating a socket for client (TCP socket)
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_server_port = 12346
tcp_server_addr_port = (server_ip, tcp_server_port)

# Connect to the TCP server
tcp_socket.connect(tcp_server_addr_port)
print("Connected to TCP SERVER:", tcp_server_addr_port)


#***************************Sockets for RTT calculation communication******************
# udpPath1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# udpPath2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# dataPath1, addrPath1 = udpPath1.sendto("Path 1 Hello".encode(), (server_ip, 11111))
# print("Connection Established for RTT calc. PATH1 - ", addrPath1)

# dataPath2, addrPath2 = udpPath2.sendto("Path 2 Hello".encode(), (server_ip2, 11111))
# print("Connection Established for RTT calc. PATH2 - ", addrPath2)


#*************Useful variables**************
frame_data = b""
expected_frame_size = 0
frames_displayed = 0
frames_sent = 0

fps, st, frame_cnt, count = (0, 0, 20, 0)
displays = 0
chunks = 0
num = 0
timestamp = ""

latency_list = [0]
socketNumber = "1"


path1Packets = 0
path2Packets = 0

temp = 0
# Create a queue for frame data
frame_queue = queue.Queue()


#Needs to be completed for RTT communication

# def rttCommunication():

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
            global socketNumber
            socketNumber = chr(int(frame_info_parts[1][0]))
            timestamp = (float)(packet[2:17].decode())
            idx = len(latency_list) - 1
            val = (int)((time.time() - latency_list[idx])*1000)
            # print("LATENCY:",val)
            latency_list[idx] = val
            latency_list.append(timestamp)
            expected_frame_size = int(frame_info_parts[1][16:].decode())
            # Remove the processed part from the buffer
            frame_info = b"".join(frame_info_parts[2:])
            if(socketNumber == "2"):
                temp += 1
        if not packet:
            break

# Create a thread to handle the reception of the initial frame size
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

# Function to receive data and manage frames
def receive_data():
    global frame_data, displays, fps, st, count, chunks, num, timestamp, frames_sent, path1Packets, path2Packets
    while True:
        packet = None
        # ret = None
        global socketNumber
        if(socketNumber == "1"):
            packet, ret = client_socket.recvfrom(BUFFER_SIZE)
            path1Packets += 1
        elif(socketNumber == "2"):
            packet, ret = client_socket2.recvfrom(BUFFER_SIZE)
            path2Packets += 1
            
        # Checking for ending-frame:
        if(packet.startswith(b'@')):
            frames_sent = (int)(packet.decode().split('@')[1])
            print("Received All Video Frames - ", frames_sent)
            # Plotting Network Latency
            latency_list.pop(0)
            latency_list.pop(len(latency_list)-1)
            x =  [i for i in range(1, len(latency_list) + 1)]
            plt.switch_backend('Agg')  
            plt.figure(figsize=(20, 10))
            plt.scatter(x, latency_list)
            plt.xlabel('Frame Number')
            plt.ylabel('Network Latency (in milliseconds)')
            plt.savefig('plot.png')
            # print("SAVED IMAGE")
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
receive_thread = threading.Thread(target=receive_data)
receive_thread.start()

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
#This {temp} variable is incremented in the receive_frame_size function
print(" Packets received on Path 2:", path2Packets, " ", temp)