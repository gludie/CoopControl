<?php

include ('coopclient.php');
?>
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <!-- The above 3 meta tags *must* come first in the head; any other head content must come *after* these tags -->
    <meta name="description" content="">
    <meta name="author" content="">
    <link rel="icon" href="../../favicon.ico">

    <title>Chicken Admin 0.1</title>

    <!-- Bootstrap core CSS -->
    <link href="./css/bootstrap.min.css" rel="stylesheet">
    <!-- Bootstrap theme -->
    <link href="./css/bootstrap-theme.min.css" rel="stylesheet">
    <!-- IE10 viewport hack for Surface/desktop Windows 8 bug -->
    <link href="./assets/css/ie10-viewport-bug-workaround.css" rel="stylesheet">

    <!-- Custom styles for this template -->
    <link href="theme.css" rel="stylesheet">

    <!-- Just for debugging purposes. Don't actually copy these 2 lines! -->
    <!--[if lt IE 9]><script src="assets/js/ie8-responsive-file-warning.js"></script><![endif]-->
    <script src="./assets/js/ie-emulation-modes-warning.js"></script>

    <!-- HTML5 shim and Respond.js for IE8 support of HTML5 elements and media queries -->
    <!--[if lt IE 9]>
      <script src="https://oss.maxcdn.com/html5shiv/3.7.2/html5shiv.min.js"></script>
      <script src="https://oss.maxcdn.com/respond/1.4.2/respond.min.js"></script>
    <![endif]-->
  </head>

  <body role="document">

    <div class="container theme-showcase" role="main">

      <!-- Main jumbotron for a primary marketing message or call to action -->
      <div class="jumbotron" style="color: #fff; background:url('background.jpg'); background-repeat: no-repeat; background-size: cover;" >
          
          <div class="row" >
              <div class="col-md-12">
                  <div class="row">
                <h1>Pippi Admin v0.1</h1>
                <p></p>            
                      </div>
              </div>
          </div>
<!-- start #get the status of GPIO 5 and display the button -->         
<?php
    if (isset($_GET['OpenDoor'])) {
        $buf = coop_send("\nopen\n");
    }
    else if (isset($_GET['CloseDoor'])) {
        $buf = coop_send("\nclose\n");
    }
    else if (isset($_GET['StopDoor'])) {
        $buf = coop_send("\nstop\n");
    }
    else if (isset($_GET['Automatic'])) {
        $buf = coop_send("\nauto\n");
    }
    else if (isset($_GET['Manual'])) {
        $buf = coop_send("\nmanual\n");
    }
    else if (isset($_GET['Halt'])) {
        $buf = coop_send("\nhalt\n");
    }
?> 

<div class="row" >
    <div class="col-md-6">
        <div class="row">
        <h3>Betriebsmodus</h3>
        </div>
        <div class="row">
        <form role="form" method="GET" action="index.php">
                      <button type="submit" class="btn btn-primary btn-lg" name="Halt"><span class="glyphicon glyphicon-stop" aria-hidden="true">HALT</button>
                      <button type="submit" class="btn btn-primary btn-lg" name="Manual"><span class="glyphicon glyphicon-pause" aria-hidden="true">MANUAL</button>
                      <button type="submit" class="btn btn-primary btn-lg" name="Automatic"><span class="glyphicon glyphicon-play" aria-hidden="true">AUTO</button>
        </form>
        </div>
    </div>
    <div class="col-md-6">
        <div class="row">
            <h3>Manuelle Türsteuerung</h3>
        </div>
        <div class="row">
            <form role="form" method="GET" action="index.php">
                      <button type="submit" class="btn btn-primary btn-lg" name="OpenDoor"><span class="glyphicon glyphicon-collapse-up" aria-hidden="true">OPEN</button>
                      <button type="submit" class="btn btn-primary btn-lg" name="CloseDoor"><span class="glyphicon glyphicon-collapse-down" aria-hidden="true">CLOSE</button>
                      <button type="submit" class="btn btn-primary btn-lg" name="StopDoor"><span class="glyphicon glyphicon-ban-circle" aria-hidden="true">STOP</button>
            </form>
            <!-- end #get the status of GPIO 5 and display the button -->
        </div> <!-- jumbotron status-->

    </div>
</div>
        </div>

        <div class="jumbotron">
<!-- start #get the status of time -->         


<a id="pipistatus"></a>
        <h2>Status</h2>
        <form role="form" method="GET" action="index.php">
          <div class="form-group">
              <button type='submit' class='btn refresh btn-block' name="status">Status aktualisieren</button>
            </div>
        </form>
                <?php

                $buf = coop_send("\nstatus\n");
                // $buf has format "\nKey1=>Value1\nKeyn=>Valuen" (pair separator = "\n", key value separator = "=>")

                $arr = explode("\n",$buf);
                // the first line is a "you sent me " info ... not relevant for status elements in table
                //unset($arr[0]);
                $td = new DateTime();
                foreach ($arr as $key => $value) {
                    //unset($arr[$key]);
                    $b = explode("=>", $value);
                    // Datum von bestimmten Zeiten trimmen
                    if (($b[0] === "Dawn") ||
                       ($b[0] === "Dusk") ||
                       ($b[0] === "Opening time") ||
                       ($b[0] === "Closing time") ||
                       ($b[0] === "Sunrise") ||
                       ($b[0] === "Sunset")) { 
                        $td->setTimestamp(strtotime($b[1]));
                        $b[1] = date_format($td,"H:i:s");
                    }
                    $arr[$b[0]] = trim($b[1]);
                    unset($arr[$key]);
                }        
                ?>
      

        <div class="col-md-6">
          <table class="table table-striped">
            <tbody>
                <tr>
                    <td>Türstatus</td>
                    <td>
                        <span class="label label-pill label-<?php echo $arr["Doorstatus"]=== 'OPEN' ? 'success' :  'default'; ?>">OPENED</span>
                        <span class="label label-pill label-<?php echo $arr["Doorstatus"]=== 'CLOSED' ? 'success' :  'default'; ?>">CLOSED</span>
                        <span class="label label-pill label-<?php echo $arr["Doorstatus"]=== 'UNKNOWN' ? 'danger' :  'default'; ?>">UNKNOWN</span>
                </tr>
                <tr>
                    <td>Modus</td>
                    <td>
                        <span class="label label-pill label-<?php echo $arr["Mode"]=== 'AUTO' ? 'success' :  'default'; ?>">AUTO</span>
                        <span class="label label-pill label-<?php echo $arr["Mode"]=== 'MANUAL' ? 'success' :  'default'; ?>">MANUAL</span>
                        <span class="label label-pill label-<?php echo $arr["Mode"]=== 'HALT' ? 'danger' :  'default'; ?>">HALT</span>
                    </tr>
                <tr>
                    <td>Türsensoren</td>
                    <td>
                        <span class="label label-pill label-<?php echo $arr["Trigger top"]=== '1' ? 'success' :  'default'; ?>">Oben</span>
                        <span class="label label-pill label-<?php echo $arr["Trigger bottom"]=== '1' ? 'success' :  'default'; ?>">Unten</span>
                </tr>
                <tr>
                    <td>Motorstatus</td>
                    <td>
                        <span class="label label-pill label-<?php echo $arr["MotorDirection"]=== '0' ? 'success' :  'default'; ?>">Leerlauf</span>
                        <span class="label label-pill label-<?php echo $arr["MotorDirection"]=== '1' ? 'success' :  'default'; ?>">Rauf</span>
                        <span class="label label-pill label-<?php echo $arr["MotorDirection"]=== '2' ? 'success' :  'default'; ?>">Runter</span>
                </tr>
            </tbody>
          </table>
        </div>
        <div class="col-md-6">
          <table class="table table-striped">
            <tbody>
                <tr>
                    <td>Aktuelle Zeit</td>
                    <td><?php echo $arr["Current time"]; ?></td>
                </tr>
                <tr>
                    <td>Morgendämmerung</td>
                    <td><?php echo $arr["Dawn"]; ?></td>
                </tr>
                <tr>
                    <td>Sonnenaufgang</td>
                    <td><?php echo $arr["Sunrise"]; ?></td>
                </tr>
                <tr>
                    <td>Autom. Tor auf</td>
                    <td class="table-success"><?php echo $arr["Opening time"]; ?></td>
                </tr>
                <tr>
                    <td>Sonnenuntergang</td>
                    <td><?php echo $arr["Sunset"]; ?></td>
                </tr>
                <tr>
                    <td>Autom. Tor zu</td>
                    <td class="table-success"><?php echo $arr["Closing time"]; ?></td>
                </tr>
                <tr>
                    <td>Abenddämmerung</td>
                    <td><?php echo $arr["Dusk"]; ?></td>
                </tr>
            </tbody>
          </table>
        </div>

<!-- end #get the status of time -->         

        <form role="form" method="GET" action="index.php">
          <div class="form-group">
              <button type='submit' class='btn refresh btn-block' name="snapshot">Foto aktualisieren</button>
            </div>
        </form>
                <?php

                if (isset($_GET['snapshot'])) {
                    $val = trim(@shell_exec("/usr/bin/python /var/www/chickens/paparazi.py"));
                    //echo $val;
                }
                ?>
        <img src="snapshot.jpg?<?php echo time(); ?>" class="img-responsive center-block" alt="Responsive image">
        <?php
            echo "<p class='text-center'>Bild wurde zuletzt erstellt: " . date("F d Y H:i:s.", filectime("snapshot.jpg")) . "</p>";
        ?>
        </div>
</div> <!-- /container -->


    <!-- Bootstrap core JavaScript
    ================================================== -->
    <!-- Placed at the end of the document so the pages load faster -->
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.11.3/jquery.min.js"></script>
    <script>window.jQuery || document.write('<script src="./assets/js/vendor/jquery.min.js"><\/script>')</script>
    <script src="./js/bootstrap.min.js"></script>
    <script src="./assets/js/docs.min.js"></script>
    <!-- IE10 viewport hack for Surface/desktop Windows 8 bug -->
    <script src="./assets/js/ie10-viewport-bug-workaround.js"></script>
  </body>
</html>
