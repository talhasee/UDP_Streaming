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

# Creating a socket for client (TCP socket)
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Creating a socket for client (UDP socket)
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Define server's address
server_ip = get_ip_address()
server_ip = "192.168.46.20"
if server_ip:
    print("IP Address:", server_ip)
else:
    print("Failed to obtain IP address. Exiting the script.")
    sys.exit(1)


server_port = 12345
tcp_server_port = 12346

server_addr_port = (server_ip, server_port)
tcp_server_addr_port = (server_ip, tcp_server_port)

# Initiating the connection with server_socket using UDP
client_socket.sendto("Initial Message".encode(), server_addr_port)

# Connect to the TCP server
tcp_socket.connect(tcp_server_addr_port)
print("Connected to TCP SERVER:", tcp_server_addr_port)

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

# Create a queue for frame data
frame_queue = queue.Queue()


def receive_frame_size():
    global expected_frame_size, latency_list, frames_sent
    frame_info = b""  # Initialize an empty buffer to store received data

    while True:
        packet = tcp_socket.recv(2000)  # Adjust buffer size if needed
        frame_info += packet  # Append the received packet to the buffer

        # Split the buffer by the delimiter "|"
        frame_info_parts = frame_info.split(b'|')

        # Process complete frame size info
        if len(frame_info_parts) > 1:

            timestamp = (float)(packet[1:16].decode())
            idx = len(latency_list) - 1
            val = (int)((time.time() - latency_list[idx])*1000)
            # print("LATENCY:",val)
            latency_list[idx] = val
            latency_list.append(timestamp)
            expected_frame_size = int(frame_info_parts[1][15:].decode())
            print("Frame parts ", frame_info_parts, " Received frame size through TCP socket:", expected_frame_size)

            # Remove the processed part from the buffer
            frame_info = b"".join(frame_info_parts[2:])

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
            # client_socket.close()
            break

# Function to receive data and manage frames
def receive_data():
    global frame_data, displays, fps, st, count, chunks, num, timestamp, frames_sent
    while True:
        packet, ret = client_socket.recvfrom(BUFFER_SIZE)
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
# cv2.destroyAllWindows()
print("Frames sent - ", frames_sent, " Frames displayed - ", frames_displayed)
packet_loss = max(0, (frames_sent - frames_displayed)*100/(frames_sent))
print("VIDEO FRAMES LOSS:", round(packet_loss,4), end =" %\n")
print("AVERAGE LATENCY:", sum(latency_list)/len(latency_list))
print("Successfully Terminated Client Program.")

plt.clf()

plt.boxplot(latency_list)

plt.xlabel("PATHS")
plt.ylabel("RTT (in ms)")
plt.title("Box plot for RTT variation")
plt.savefig("BoxPlot_latency")