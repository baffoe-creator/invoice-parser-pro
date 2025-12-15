// Minimal frontend snippets to call v2 endpoints.
// Use fetch to upload and to apply edits / request webhook.
async function parseFile(file){
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/api/v2/invoices/parse', { method: 'POST', body: fd });
  const json = await res.json();
  // render parsed json.parsed and show confidences
  return json;
}

async function patchField(invoice_id, field_name, value){
  const res = await fetch(`/api/v2/invoices/${invoice_id}/fields/${field_name}`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({value, source: 'manual'})
  });
  return res.json();
}

async function enqueueWebhook(invoice_id, webhook_url, secret){
  const res = await fetch(`/api/v2/invoices/${invoice_id}/webhook`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({webhook_url, secret})
  });
  return res.json();
}

async function approve(invoice_id){
  const res = await fetch(`/api/v2/invoices/${invoice_id}/approve`, { method: 'POST' });
  if (res.headers.get('Content-Disposition')) {
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `invoice_${invoice_id}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } else {
    const json = await res.json();
    if (json.download_url) window.open(json.download_url);
  }
}