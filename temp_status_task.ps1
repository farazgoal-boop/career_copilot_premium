$f1='ready to client\career-copilot-premium-setup.exe'
$f2='ready to client\career-copilot-premium.apk'
$f3='release\installer\current\CareerCopilotPremium_Setup_CURRENT.exe'
foreach($f in @($f1,$f2,$f3)){
 if(Test-Path $f){ $i=Get-Item $f; Write-Output ($f+'|'+$i.Length+'|'+$i.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')) }
 else { Write-Output ('MISSING|'+$f) }
}
