# gunshield
Hacktech 2018: Project Gunshield

Project Overview
A camera and accelerometer mounted on a firearm sends live video to computer vision processing, which then detects if people are present or if the camera is being covered. In either scenario, a signal to lock the firearm and stop it from firing is given. If the trigger is pulled while the gun is pointed at people, emergency services are notified via automated phone calls giving the exact location of the incident (from a GPS sensor). This entire process is simulated in real-time on a VR environment, enabling rapid prototyping.

analyze_cam_universal.py: streams video feed from IP Webcam Android app and searches for people with Microsoft Computer Vision API. Records results in text file easily readable by Unity platform for visualization in Oculus Rift VR.
location.php: reads GPS location from text file on server then calls and texts phone numbers with the Twilio API alerting of shooting.
dragonboard: reads GPS location Qualcomm Dragonboard 410C with option to hardcode a test gps coordinate then calls the Google Maps API to write street location to text file.
