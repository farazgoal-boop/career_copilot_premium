$files=@('ready to client\career-copilot-premium-setup.exe','ready to client\career-copilot-premium.apk')
foreach($f in $files){
 if(Test-Path $f){$i=Get-Item $f; Write-Output ($f+'|'+$i.Length+'|'+$i.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))}
 else {Write-Output ('MISSING|'+$f)}
}
