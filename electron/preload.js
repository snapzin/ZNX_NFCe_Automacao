const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  apiCall: (method, endpoint, body = null) =>
    ipcRenderer.invoke('api-call', method, endpoint, body),
  selectFolder: () =>
    ipcRenderer.invoke('select-folder'),
  selectFile: () =>
    ipcRenderer.invoke('select-file'),
  selectCertificate: () =>
    ipcRenderer.invoke('select-certificate'),
  openResult: (jobId, tipo, cnpj = '') =>
    ipcRenderer.invoke('open-result', jobId, tipo, cnpj),
});
