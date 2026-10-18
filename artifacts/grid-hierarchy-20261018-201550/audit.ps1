$ErrorActionPreference='Stop'
$taskDirectory=Split-Path -Parent $MyInvocation.MyCommand.Path
& agent-browser --session grid-layer open http://127.0.0.1:8016/ | Out-Null
& agent-browser --session grid-layer wait --fn 'document.querySelector("#histZoom").dataset.yTicks!==undefined' | Out-Null
foreach($taskViewport in @(@(1920,950),@(1536,760),@(1280,620))){
  & agent-browser --session grid-layer set viewport $taskViewport[0] $taskViewport[1] | Out-Null
  & agent-browser --session grid-layer eval 'document.querySelector("#histZoom").scrollIntoView({block:"center"})' | Out-Null
  foreach($taskTheme in @('light','dark')){
    $taskCode='document.documentElement.dataset.auditTheme="'+$taskTheme+'";'+[IO.File]::ReadAllText((Join-Path $taskDirectory 'check-grid.js'))
    $taskEncoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($taskCode))
    $taskOutput=& agent-browser --session grid-layer eval -b $taskEncoded --json
    $taskResult=$taskOutput | ConvertFrom-Json
    $taskName='histogram-'+$taskViewport[0]+'-'+$taskTheme
    [IO.File]::WriteAllText((Join-Path $taskDirectory ($taskName+'.json')),($taskOutput -join "`n"))
    if(-not $taskResult.success){throw ($taskName+': '+$taskResult.error)}
    & agent-browser --session grid-layer screenshot (Join-Path $taskDirectory ($taskName+'.png')) | Out-Null
    Write-Output ($taskName+' PASS')
  }
}
