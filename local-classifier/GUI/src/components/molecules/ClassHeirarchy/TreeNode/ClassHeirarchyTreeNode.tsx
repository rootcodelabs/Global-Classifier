import { FormInput } from 'components/FormElements';
import React, { ChangeEvent, useState } from 'react';
import { TreeNode } from 'types/datasetGroups';
import { isClassHierarchyDuplicatedAtSameLevel } from 'utils/datasetGroupsUtils';
import { MdDeleteOutline } from 'react-icons/md';
import { useTranslation } from 'react-i18next';
import './ClassHeirarchyTreeNode.scss';

const ClassHeirarchyTreeNode = ({
  node,
  onAddSubClass,
  onDelete,
  setNodesError,
  nodesError,
  nodes,
}: {
  onAddSubClass: (parentId: number | string) => void;
  onDelete: (nodeId: number | string) => void;
  setNodesError: React.Dispatch<React.SetStateAction<boolean>>;
  nodes?: TreeNode[];
  node: TreeNode;
  nodesError?: boolean;
}) => {
  const { t } = useTranslation();

  const [fieldName, setFieldName] = useState(node.fieldName);

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setFieldName(e.target.value);
    node.fieldName = e.target.value;
    if (isClassHierarchyDuplicatedAtSameLevel(nodes, e.target.value)) setNodesError(true);
    else setNodesError(false);
  };

  return (
    <div
      className="container-wrapper"
      style={{
        marginLeft: node.level * 20,
      }}
    >
      <div className="class-grid">
        <div>
          <FormInput
            label=""
            name="className"
            placeholder={t('datasetGroups.classHierarchy.fieldHint') ?? ''}
            value={fieldName}
            onChange={handleChange}
            error={
              nodesError && !fieldName
                ? t('datasetGroups.classHierarchy.fieldHint') ?? ''
                : fieldName && isClassHierarchyDuplicatedAtSameLevel(nodes, fieldName)
                ? t('datasetGroups.classHierarchy.filedHintIfExists') ?? ''
                : ''
            }
            aria-autocomplete='none'
          />
        </div>
        <div
          onClick={() => onAddSubClass(node?.id)}
          className="underlined-link"
        >
          {t('datasetGroups.classHierarchy.addSubClass')}
        </div>
        <div
          onClick={() => onDelete(node?.id)}
          className="link"
        >
          <MdDeleteOutline /> {t('global.delete')}
        </div>
      </div>
      {node?.children &&
        node?.children?.map((child) => (
          <ClassHeirarchyTreeNode
            key={child?.id}
            node={child}
            onAddSubClass={onAddSubClass}
            onDelete={onDelete}
            nodes={nodes}
            setNodesError={setNodesError}
          />
        ))}
    </div>
  );
};

export default ClassHeirarchyTreeNode;