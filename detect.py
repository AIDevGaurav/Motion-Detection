import cv2
import time
import threading

rtsp_url = "rtsp://admin:admin@789@192.168.1.199:554/unicast/c1/s0/live"  # Replace with your RTSP URL

def capture_image(frame):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    image_filename = f"motion_{timestamp}.jpg"
    cv2.imwrite(image_filename, frame)
    print(f"Captured image: {image_filename}")

def capture_video(rtsp_url):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    video_filename = f"motion_{timestamp}.avi"
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

def detectMotion():
    cap = cv2.VideoCapture(rtsp_url)

    # Parameters for motion detection
    threshold_value = 5
    min_area_full_frame = 50

    # Define the Rate Of Interest (top-left and bottom-right corners)
    roi_top_left = (250, 200)
    roi_bottom_right = (550, 400)

    # Calculate ROI dimensions
    roi_width = roi_bottom_right[0] - roi_top_left[0]
    roi_height = roi_bottom_right[1] - roi_top_left[1]
    roi_area = roi_width * roi_height

    # Adjust min_area for the ROI
    full_frame_width = 1920
    full_frame_height = 1080
    full_frame_area = full_frame_width * full_frame_height

    min_area = (min_area_full_frame / full_frame_area) * roi_area

    # Initialize previous frame
    ret, frame = cap.read()
    if not ret:
        print("Failed to read the stream.")
        return

    frame = cv2.resize(frame, None, fx=0.4, fy=0.4)
    roi_frame = frame[roi_top_left[1]:roi_bottom_right[1], roi_top_left[0]:roi_bottom_right[0]]
    prev_frame_gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
    prev_frame_gray = cv2.GaussianBlur(prev_frame_gray, (21, 21), 0)

    last_detection_time = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.resize(frame, None, fx=0.4, fy=0.4)
        display_frame = frame.copy()  # Copy for displaying with rectangles
        roi_frame = frame[roi_top_left[1]:roi_bottom_right[1], roi_top_left[0]:roi_bottom_right[0]]
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
        if motion_detected and (current_time - last_detection_time > 60): #replace 60 with your desired second delay....
            cv2.putText(display_frame, "Motion Detected", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # Capture image
            threading.Thread(target=capture_image, args=(frame.copy(),)).start()

            # Capture video
            threading.Thread(target=capture_video, args=(rtsp_url,)).start()

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

detectMotion()
