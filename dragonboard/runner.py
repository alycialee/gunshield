import subprocess, signal, os, sys, pynmea2, time, json, urllib, random, socket
from datetime import date as dt

socket.setdefaulttimeout(2)

def getData(live=False):
    if(live):
        proc = subprocess.Popen('cat</dev/ttyGPS0 > _output2', shell=True)
        time.sleep(2)
        os.kill(int(proc.pid), signal.SIGTERM)

    f = open('_output2', 'r')
    for line in f:
        if('$GPGGA' in line):
            l2 = line.replace('\x00', '')
            l2 = l2.replace('\n', '')
            locdict = pynmea2.parse(l2)
            return locdict.latitude, locdict.longitude

f = open('address', 'w')

try:
    glat, glon = getData(live=True)
except:
    f.write("not a valid address")
    sys.exit(0)

#hardcode to LA area, CA
glat, glon = 34.1377+(random.random()*0.02-0.01), -118.1249+(random.random()*0.02-0.01)
url = 'http://maps.googleapis.com/maps/api/geocode/json?latlng='+str(glat)+','+str(glon)
print(url)

try:
    txt = json.load(urllib.urlopen(url))
except:
    f.write("")
    sys.exit(0)
    
address = ""
try:
    for cmpt in txt['results'][0]['address_components']:
        address += cmpt['long_name'] + " "
    f.write(address)
except:
    f.write("not a valid address")
    sys.exit(0)
