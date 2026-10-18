param([string]$Only='')
$ErrorActionPreference='Stop'
$taskDirectory=Split-Path -Parent $MyInvocation.MyCommand.Path
$taskAuditSource=[IO.File]::ReadAllText((Join-Path $taskDirectory 'browser-audit.js'))
$taskPages=@(
  @{key='spad';path='/spad';ready='document.querySelectorAll("[data-path]").length>0'},
  @{key='budget';path='/system/budget';ready='document.querySelector("#formState").textContent.includes("计算完成")'},
  @{key='a';path='/';ready='document.querySelector("[data-key=range_m]").value!==""'},
  @{key='b';path='/system';ready='document.body.dataset.ready==="true"'},
  @{key='c';path='/system/scan';ready='document.body.dataset.ready==="true"'}
)
foreach($taskPage in $taskPages){
  if($Only -and $taskPage.key -notin $Only.Split(',')){continue}
  & agent-browser --session ui-review open ('http://127.0.0.1:18767'+$taskPage.path) | Out-Null
  & agent-browser --session ui-review wait --fn $taskPage.ready | Out-Null
  foreach($taskViewport in @(@(1920,950),@(1536,760),@(1280,620))){
    & agent-browser --session ui-review set viewport $taskViewport[0] $taskViewport[1] | Out-Null
    foreach($taskTheme in @('dark','light')){
      $taskCode='document.documentElement.dataset.auditTheme="'+$taskTheme+'";'+$taskAuditSource
      $taskEncoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($taskCode))
      $taskOutput=& agent-browser --session ui-review eval -b $taskEncoded --json
      $taskResult=$taskOutput | ConvertFrom-Json
      $taskName=$taskPage.key+'-'+$taskViewport[0]+'-'+$taskTheme
      [IO.File]::WriteAllText((Join-Path $taskDirectory ($taskName+'.json')),($taskOutput -join "`n"))
      if(-not $taskResult.success){throw ($taskName+': '+$taskResult.error)}
      & agent-browser --session ui-review screenshot (Join-Path $taskDirectory ($taskName+'.png')) | Out-Null
      Write-Output ($taskName+' PASS')
    }
  }
}
