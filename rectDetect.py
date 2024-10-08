import cv2
import os
import time
import threading
import paho.mqtt.client as mqtt  # type: ignore

# MQTT configuration
broker = "broker.hivemq.com"  # Replace with your MQTT broker address
port = 1883  # Replace with your MQTT broker port
topic = "motion/detection"

# Define the MQTT client callbacks
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(topic)  # Subscribe to the topic when connected

def on_message(client, userdata, msg):
    print(f"Received message: {msg.topic} -> {msg.payload.decode()}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print("Unexpected disconnection.")
    else:
        print("Disconnected successfully.")

# Initialize MQTT client and set up callbacks
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.on_disconnect = on_disconnect

# Connect to the broker
mqtt_client.connect(broker, port, 60)

# Function to publish a message
def publish_message(message):
    mqtt_client.publish(topic, message)
    print(f"Published message: {message}")

# Start the MQTT client loop in a separate thread
mqtt_client.loop_start()

# Ensure directories exist
image_dir = "images"
video_dir = "videos"
os.makedirs(image_dir, exist_ok=True)
os.makedirs(video_dir, exist_ok=True)

# Function to capture an image
def capture_image(frame):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    image_filename = os.path.join(image_dir, f"motion_{timestamp}.jpg")
    cv2.imwrite(image_filename, frame)
    print(f"Captured image: {image_filename}")

# Function to capture a video
def capture_video(rtsp_url):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    video_filename = os.path.join(video_dir, f"motion_{timestamp}.avi")
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    cap_video = cv2.VideoCapture(rtsp_url)
    width = int(cap_video.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap_video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(video_filename, fourcc, 20.0, (width, height))

    start_time = time.time()
    while int(time.time() - start_time) < 5:
        ret, frame = cap_video.read()
        if not ret:
            break
        out.write(frame)

    cap_video.release()
    out.release()
    print(f"Captured video: {video_filename}")

# Function to detect motion
def detect_motion(rtsp_url, camera_id, coordinates):
    print(f"Starting motion detection on Camera ID {camera_id} with RTSP URL {rtsp_url}")
    print(f"Using coordinates: {coordinates}")
    
    cap = cv2.VideoCapture(rtsp_url)

    # Parameters for motion detection
    threshold_value = 16
    min_area_full_frame = 1200

    # Initialize previous frame
    ret, frame = cap.read()
    if not ret:
        print("Failed to read the stream.")
        return

    original_height, original_width = frame.shape[:2]

    # Desired display size (adjust this as needed)
    display_width = 800
    display_height = 600

    # Calculate the resizing factors dynamically
    fx = display_width / original_width
    fy = display_height / original_height

    # Resize the frame
    frame = cv2.resize(frame, (display_width, display_height))
    frame_height, frame_width = frame.shape[:2]

    # Define the ROI based on the resized frame
    roi_top_left = (int(coordinates["x"] * fx), int(coordinates["y"] * fy))
    roi_bottom_right = (int((coordinates["x"] + coordinates["width"]) * fx), int((coordinates["y"] + coordinates["height"]) * fy))

    # Adjust ROI if it goes out of bounds
    roi_top_left = (max(0, roi_top_left[0]), max(0, roi_top_left[1]))
    roi_bottom_right = (min(frame_width, roi_bottom_right[0]), min(frame_height, roi_bottom_right[1]))

    # Ensure the adjusted ROI is valid
    if roi_bottom_right[0] <= roi_top_left[0] or roi_bottom_right[1] <= roi_top_left[1]:
        print("Invalid ROI after adjustment. Defaulting to full frame.")
        roi_top_left = (0, 0)
        roi_bottom_right = (frame_width, frame_height)
    
    roi_width = roi_bottom_right[0] - roi_top_left[0]
    roi_height = roi_bottom_right[1] - roi_top_left[1]
    roi_area = roi_width * roi_height

    full_frame_area = original_width * original_height
    min_area = (min_area_full_frame / full_frame_area) * roi_area

    # Extract the ROI from the frame
    roi_frame = frame[roi_top_left[1]:roi_bottom_right[1], roi_top_left[0]:roi_bottom_right[0]]

    if roi_frame is None or roi_frame.size == 0:
        print("Error: ROI frame is empty or invalid.")
        return

    prev_frame_gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
    prev_frame_gray = cv2.GaussianBlur(prev_frame_gray, (21, 21), 0)

    last_detection_time = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Resize the frame based on the same factors
        frame = cv2.resize(frame, (display_width, display_height))
        display_frame = frame.copy()  # Copy for displaying with rectangles

        roi_frame = frame[roi_top_left[1]:roi_bottom_right[1], roi_top_left[0]:roi_bottom_right[0]]

        if roi_frame is None or roi_frame.size == 0:
            print("Error: ROI frame is empty or invalid during processing.")
            break

        gray_frame = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
        gray_frame = cv2.GaussianBlur(gray_frame, (21, 21), 0)

        frame_diff = cv2.absdiff(prev_frame_gray, gray_frame)
        _, thresh_frame = cv2.threshold(frame_diff, threshold_value, 255, cv2.THRESH_BINARY)
        thresh_frame = cv2.dilate(thresh_frame, None, iterations=2)

        contours, _ = cv2.findContours(thresh_frame.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion_detected = False

        for contour in contours:
            if cv2.contourArea(contour) > min_area:
                (x, y, w, h) = cv2.boundingRect(contour)
                full_frame_x = x + roi_top_left[0]
                full_frame_y = y + roi_top_left[1]
                cv2.rectangle(display_frame, (full_frame_x, full_frame_y), (full_frame_x + w, full_frame_y + h), (0, 255, 0), 2)
                motion_detected = True

        current_time = time.time()
        if motion_detected and (current_time - last_detection_time > 10):  # replace 10 with your desired second delay....
            cv2.putText(display_frame, "Motion Detected", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # Capture image
            threading.Thread(target=capture_image, args=(frame.copy(),)).start()

            # Capture video
            threading.Thread(target=capture_video, args=(rtsp_url,)).start()

            # Publish MQTT message
            threading.Thread(target=publish_message, args=("Motion detected!",)).start()

            last_detection_time = current_time

        # Draw ROI rectangle on the display frame
        cv2.rectangle(display_frame, roi_top_left, roi_bottom_right, (255, 0, 0), 2)

        # Display frame
        cv2.imshow("Motion Detection", display_frame)

        prev_frame_gray = gray_frame

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        if cv2.getWindowProperty('Motion Detection', cv2.WND_PROP_VISIBLE) < 1:
            break

    cap.release()
    cv2.destroyAllWindows()

# Example usage:
if __name__ == '__main__':
    # Example values for manual testing
    rtsp_url = "rtsp://admin:admin@789@192.168.1.199:554/unicast/c1/s0/live"
    camera_id = 20
    coordinates = {"x": 650, "y": 500, "width": 300, "height": 300}
    detect_motion(rtsp_url, camera_id, coordinates)

# Stop the MQTT client loop and disconnect
mqtt_client.loop_stop()
mqtt_client.disconnect()
