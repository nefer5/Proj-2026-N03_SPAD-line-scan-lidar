$ErrorActionPreference='Stop'
$taskDirectory=Split-Path -Parent $MyInvocation.MyCommand.Path
foreach($taskPage in @('budget','histogram')){
  $taskPath=if($taskPage -eq 'budget'){'/system/budget'}else{'/'}
  & agent-browser --session plot-fix open ('http://127.0.0.1:8016'+$taskPath) | Out-Null
  if($taskPage -eq 'budget'){
    & agent-browser --session plot-fix wait --fn 'document.querySelector("#sceneWorldAxes text")!==null' | Out-Null
  }else{
    & agent-browser --session plot-fix wait --fn 'document.querySelector("#histZoom").dataset.yTicks!==undefined' | Out-Null
  }
  foreach($taskViewport in @(@(1920,950),@(1536,760),@(1280,620))){
    & agent-browser --session plot-fix set viewport $taskViewport[0] $taskViewport[1] | Out-Null
    $taskSelector=if($taskPage -eq 'budget'){'#sceneViewport'}else{'#histZoom'}
    & agent-browser --session plot-fix eval ('document.querySelector("'+$taskSelector+'").scrollIntoView({block:"center"})') | Out-Null
    foreach($taskTheme in @('light','dark')){
      $taskSource=[IO.File]::ReadAllText((Join-Path $taskDirectory ('check-'+$taskPage+'.js')))
      $taskCode='document.documentElement.dataset.auditTheme="'+$taskTheme+'";'+$taskSource
      $taskEncoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($taskCode))
      $taskOutput=& agent-browser --session plot-fix eval -b $taskEncoded --json
      $taskResult=$taskOutput | ConvertFrom-Json
      $taskName=$taskPage+'-'+$taskViewport[0]+'-'+$taskTheme
      [IO.File]::WriteAllText((Join-Path $taskDirectory ($taskName+'.json')),($taskOutput -join "`n"))
      if(-not $taskResult.success){throw ($taskName+': '+$taskResult.error)}
      & agent-browser --session plot-fix screenshot (Join-Path $taskDirectory ($taskName+'.png')) | Out-Null
      Write-Output ($taskName+' PASS')
    }
  }
}
