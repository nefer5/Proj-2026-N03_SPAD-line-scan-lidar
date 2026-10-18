/* Explicit project defaults; ordinary editing remains a browser draft. */
globalThis.ProjectDefaults = (() => {
  async function request(kind, action, config, revision) {
    const response = await fetch(`/api/defaults/${kind}/${action}`, {
      method: 'POST', cache: 'no-store', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({config, ...(revision ? {revision} : {})})
    });
    const result = await response.json();
    if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail));
    return result;
  }
  function bind(kind, collect, resetId) {
    const reset = document.getElementById(resetId);
    const button = document.createElement('button');
    button.id = 'saveDefaults'; button.type = 'button'; button.textContent = '设为默认';
    button.title = '预览变更与影响范围，再写回 config/defaults.yaml';
    reset.after(button);
    const status = document.createElement('p');
    status.id = 'defaultSaveStatus'; status.role = 'status'; status.className = 'defaults-status';
    reset.parentElement.after(status);
    const dialog = document.createElement('dialog');
    dialog.className = 'defaults-dialog'; dialog.setAttribute('aria-labelledby', 'defaultsTitle');
    dialog.innerHTML = '<h2 id="defaultsTitle">设为项目默认配置</h2><p>共享参数会影响继承它的平台。已有任务和其他已打开的表单保持原配置；点击“恢复默认”读取新值。</p><p id="defaultImpact"></p><div class="defaults-table"><table><thead><tr><th>参数 / YAML归属</th><th>原值</th><th>新值</th></tr></thead><tbody></tbody></table></div><p id="defaultWriteState" role="status"></p><div class="defaults-actions"><button type="button" id="cancelDefaults">取消</button><button type="button" id="confirmDefaults">确认写入默认配置</button></div>';
    document.body.append(dialog);
    const confirm = dialog.querySelector('#confirmDefaults'), message = dialog.querySelector('#defaultWriteState');
    let pending, saving = false;
    const close = () => { if (!saving) dialog.close(); };
    dialog.querySelector('#cancelDefaults').onclick = close;
    dialog.addEventListener('cancel', event => { if (saving) event.preventDefault(); });
    button.onclick = async () => {
      button.disabled = true; status.textContent = '正在校验默认配置与跨平台影响…';
      try {
        // Freeze exactly what the user reviewed, even if a live calculation updates the form.
        const config = structuredClone(collect());
        const preview = await request(kind, 'preview', config);
        if (preview.unchanged) { status.textContent = '当前参数与默认配置一致，无需写入。'; return; }
        pending = {config, revision: preview.revision};
        dialog.querySelector('#defaultImpact').textContent = '影响范围：' + preview.affected.map(x => `${x.label}（${x.count}项）`).join('、');
        const rows = dialog.querySelector('tbody'); rows.replaceChildren();
        const format = value => JSON.stringify(value);
        for (const change of preview.changes) {
          const row = document.createElement('tr');
          for (const value of [change.parameter + '\n' + change.source, format(change.before), format(change.after)]) {
            const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
          }
          rows.append(row);
        }
        message.textContent = '写入前自动备份原 YAML；所有平台默认配置须通过校验。';
        status.textContent = '请审查变更后确认写入。'; confirm.disabled = false; dialog.showModal();
      } catch (error) { status.textContent = '未保存：' + error.message; }
      finally { button.disabled = false; }
    };
    confirm.onclick = async () => {
      saving = true; confirm.disabled = true; button.disabled = true;
      message.textContent = '正在校验并保存…';
      try {
        const result = await request(kind, 'save', pending.config, pending.revision);
        status.textContent = result.unchanged ? '配置未变化。' : `已写入 config/defaults.yaml。备份：${result.backup}。恢复默认可读取新值；已有任务不受影响。`;
        dialog.close();
      } catch (error) {
        message.textContent = '未保存：' + error.message + ' 关闭后可重新预览。';
        status.textContent = '默认配置未保存：' + error.message;
      } finally { saving = false; button.disabled = false; }
    };
  }
  return {bind};
})();
