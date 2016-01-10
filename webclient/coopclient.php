<?php

define('COOPSERVER', 'localhost');
define('COOPPORT',55567);
    
function coop_send($message) {
    if(!($sock = socket_create(AF_INET, SOCK_STREAM, 0)))
    {
        $errorcode = socket_last_error();
        $errormsg = socket_strerror($errorcode);

        die("Couldn't create socket: [$errorcode] $errormsg \n");
    }

    //Connect socket to remote server
    if(!socket_connect($sock , COOPSERVER , COOPPORT))
    {
        $errorcode = socket_last_error();
        $errormsg = socket_strerror($errorcode);

        die("Could not connect: [$errorcode] $errormsg \n");
    }

    //Send the message to the server
    if( ! socket_send ( $sock , $message , strlen($message) , 0))
    {
        $errorcode = socket_last_error();
        $errormsg = socket_strerror($errorcode);

        die("Could not send data: [$errorcode] $errormsg \n");
    }

    $buf = 'my buffer';
    if (false !== ($bytes = socket_recv($sock, $buf, 1024, 0))) {
        echo "Read $bytes bytes of socket_recv(). close socket ...";
    } else {
        echo "socket_recv() error; Reason: " . socket_strerror(socket_last_error($socket)) . "\n";
    }
    socket_close($sock);

    return $buf;
    
}

?>