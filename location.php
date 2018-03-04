<?php
$home = '/home/gpsuser/';
// Required if your environment does not handle autoloading
require $home . 'vendor/autoload.php';
// Use the REST API Client to make requests to the Twilio REST API
use Twilio\Rest\Client;

// Your Account SID and Auth Token from twilio.com/console
$sid = 'AC4366e2744d3f1fd039fd4b4db36d60c0';
$token = '1263d9cf1d8f6f44d717a43aaff03b61';

$client = new Client($sid, $token);

$file = fopen($home.'gpslogs/log.txt', 'r') or die('Unable to open gps log file');
$loc = fread($file, filesize($home.'gpslogs/log.txt'));
fclose($file);

$police = 'ALERT to all active units: Active shooting attempt at' . $loc . '.';
$xml = new DOMDocument('1.0');
$response = $xml->createElement('Response');
$response = $xml->appendChild($response);
$say = $xml->createElement('Say');
$say->setAttribute('voice', 'alice');
$say->nodeValue = $police;
$response->appendChild($say);
echo $xml->save('./twilio.xml');

$people = 'The following is a message from your local police station. Please be advised: there is an attempted active shooting attempt reported at ' . $loc . '. Please locate the nearest shelter. Thank you.';


// Use the client to do fun stuff like send text messages!
$client->messages->create(
    // the number you'd like to send the message to
    '+19253099700',
    array(
        // A Twilio phone number you purchased at twilio.com/console
        'from' => '+12673146105',
        // the body of the text message you'd like to send
        'body' => $people
    )
);
$client->account->calls->create(  
    '+16692379199',
    '+12673146105',
    array(
        "url" => "http://131.215.159.127/twilio.xml"
    )
);
?>