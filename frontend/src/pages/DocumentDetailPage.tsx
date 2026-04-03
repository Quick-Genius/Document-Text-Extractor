import { useParams } from 'react-router-dom';
import { DocumentDetail } from '../components/detail/DocumentDetail';

export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();

  if (!id) return null;

  return (
    <div className="flex-grow pt-32 pb-20 max-w-7xl mx-auto w-full">
      <DocumentDetail documentId={id} />
    </div>
  );
}
