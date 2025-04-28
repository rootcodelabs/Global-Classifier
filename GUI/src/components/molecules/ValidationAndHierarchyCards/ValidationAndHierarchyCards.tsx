import React from 'react';
import ValidationCriteriaRowsView from '../ValidationCriteria/RowsView';
import { useTranslation } from 'react-i18next';
import { Card } from 'components';
import ClassHierarchy from '../ClassHeirarchy';
import { TreeNode, ValidationRule } from 'types/datasetGroups';

const ValidationAndHierarchyCards = ({
  metadata,
  isMetadataLoading,
  validationRules,
  setValidationRules,
  validationRuleError,
  setValidationRuleError,
  nodes,
  setNodes,
  nodesError,
  setNodesError,
}: {
  metadata: any;
  isMetadataLoading: boolean;
  validationRules: ValidationRule[] | undefined;
  setValidationRules: React.Dispatch<
    React.SetStateAction<ValidationRule[] | undefined>
  >;
  validationRuleError: boolean;
  setValidationRuleError: React.Dispatch<React.SetStateAction<boolean>>;
  nodes: TreeNode[];
  setNodes: React.Dispatch<any>;
  nodesError: boolean;
  setNodesError: React.Dispatch<React.SetStateAction<boolean>>;
}) => {
  const { t } = useTranslation();
  return (
    <>
      {metadata && (
        <div>
          <Card
            header={t('datasetGroups.detailedView.validationsTitle') ?? ''}
            isHeaderLight={false}
          >
            <ValidationCriteriaRowsView
              validationRules={validationRules}
              setValidationRules={setValidationRules}
              validationRuleError={validationRuleError}
              setValidationRuleError={setValidationRuleError}
            />
          </Card>

          <Card
            header={t('datasetGroups.detailedView.classHierarchy') ?? ''}
            isHeaderLight={false}
          >
            {!isMetadataLoading && (
              <ClassHierarchy
                nodes={nodes}
                setNodes={setNodes}
                nodesError={nodesError}
                setNodesError={setNodesError}
              />
            )}
          </Card>
        </div>
      )}
    </>
  );
};

export default ValidationAndHierarchyCards;
