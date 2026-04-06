import type { AxiosInstance } from 'axios';

/**
 * Get dashboard statistics
 */
export const getDashboardStats = async (api: AxiosInstance) => {
  const response = await api.get('/documents/stats/dashboard');
  return response.data;
};

/**
 * Step 1: Upload documents to server storage (no processing yet)
 */
export const uploadDocuments = async (
  api: AxiosInstance,
  files: File[],
  onProgress?: (progress: number) => void
) => {
  const formData = new FormData();
  files.forEach(file => {
    formData.append('files', file);
  });

  const response = await api.post('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      const percentCompleted = Math.round(
        (progressEvent.loaded * 100) / (progressEvent.total ?? 1)
      );
      if (onProgress) onProgress(percentCompleted);
    }
  });

  return response.data;
};

/**
 * Step 2: Trigger AI processing on an already-uploaded document
 */
export const processDocument = async (api: AxiosInstance, documentId: string) => {
  const response = await api.post(`/documents/${documentId}/process`);
  return response.data;
};

/**
 * Step 2 (batch): Trigger AI processing on multiple uploaded documents
 */
export const processDocumentsBatch = async (api: AxiosInstance, documentIds: string[]) => {
  const response = await api.post('/documents/process-batch', { document_ids: documentIds });
  return response.data;
};

export const getDocuments = async (api: AxiosInstance, filters: any) => {
  const response = await api.get('/documents', { params: filters });
  return response.data;
};

export const getDocumentById = async (api: AxiosInstance, id: string) => {
  const response = await api.get(`/documents/${id}`);
  return response.data;
};

export const deleteDocument = async (api: AxiosInstance, id: string, permanent: boolean = false) => {
  const response = await api.delete(`/documents/${id}`, { params: { permanent } });
  return response.data;
};

export const updateProcessedData = async (api: AxiosInstance, id: string, data: any) => {
  const response = await api.put(`/documents/${id}/processed-data`, data);
  return response.data;
};

export const finalizeDocument = async (api: AxiosInstance, id: string) => {
  const response = await api.post(`/documents/${id}/finalize`);
  return response.data;
};

/**
 * Cancel a document that is currently processing or queued
 */
export const cancelDocument = async (api: AxiosInstance, documentId: string) => {
  const response = await api.post(`/documents/${documentId}/cancel`);
  return response.data;
};

/**
 * Retry processing for a failed document
 */
export const retryDocument = async (api: AxiosInstance, documentId: string) => {
  const response = await api.post(`/documents/${documentId}/retry`);
  return response.data;
};
