import { FC } from 'react';
import { useTranslation } from 'react-i18next';
import NoDataView from 'components/molecules/NoDataView';
import { useDataGenerationSessions } from 'hooks/useDataGenerationSessions';
import DataGenerationSessionCard from 'components/molecules/DataGenerationSessionCard';

const DataGenerationSessions: FC = () => {
  const { t } = useTranslation();
  const progresses = useDataGenerationSessions();

  return (
    <div>
      <div className="container">
        <div className="title_container">
          <div className="title">{t('validationSessions.title')}</div>
        </div>
        {progresses?.length === 0 && (
          <NoDataView text={t('validationSessions.noSessions') ?? ''} />
        )}
        {progresses?.map((session) => (
          <DataGenerationSessionCard
            key={session.id}
            dgName={session.groupName}
            version={`V${session?.majorVersion}.${session?.minorVersion}`}
            isLatest={session.latest}
            status={session.generationStatus}
            validationMessage={session.generationMessage}
            progress={session.progressPercentage}
          />
        ))}
      </div>
    </div>
  );
};

export default DataGenerationSessions;
