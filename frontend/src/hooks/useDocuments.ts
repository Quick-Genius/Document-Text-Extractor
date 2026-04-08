import { useQuery } from '@tanstack/react-query';
import { getDocuments, getDocumentById } from '../services/documentService';
import { useApi } from './useApi';

export const useDocuments = (filters: any) => {
  const api = useApi();
  return useQuery({
    queryKey: ['documents', filters],
    queryFn: () => getDocuments(api, filters),
    staleTime: 5_000,
    refetchInterval: 3000,
  });
};

export const useDocument = (id: string) => {
  const api = useApi();
  return useQuery({
    queryKey: ['document', id],
    queryFn: () => getDocumentById(api, id),
    enabled: !!id,
    staleTime: 5_000,
    refetchInterval: 3000,
    refetchOnWindowFocus: false,
  });
};
