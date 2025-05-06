import React, { FC, PropsWithChildren, useState } from 'react';
import Button from 'components/Button';
import { v4 as uuidv4 } from 'uuid';
import './TreeNode.scss';
import Dialog from 'components/Dialog';
import { Class, TreeNode } from 'types/datasetGroups';
import { useTranslation } from 'react-i18next';
import { ButtonAppearanceTypes } from 'enums/commonEnums';
import ClassHeirarchyTreeNode from './TreeNode/ClassHeirarchyTreeNode';

type ClassHierarchyProps = {
  nodes: TreeNode[];
  setNodes: React.Dispatch<React.SetStateAction<Class[] | []>>;
  nodesError?: boolean;
  setNodesError: React.Dispatch<React.SetStateAction<boolean>>;
};

const ClassHierarchy: FC<PropsWithChildren<ClassHierarchyProps>> = ({
  nodes,
  setNodes,
  nodesError,
  setNodesError,
}) => {
  const { t } = useTranslation();
  const [currentNode, setCurrentNode] = useState<TreeNode | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const addMainClass = () => {
    setNodes([
      ...nodes,
      { id: uuidv4(), fieldName: '', level: 0, children: [] },
    ]);
  };

  const addSubClass = (parentId: number | string) => {
    const addSubClassRecursive = (nodes: TreeNode[]): TreeNode[] => {
      return nodes?.map((node: TreeNode) => {
        if (node.id === parentId) {
          const newNode = {
            id: uuidv4(),
            fieldName: '',
            level: node.level + 1,
            children: [],
          };
          return { ...node, children: [...node.children, newNode] };
        }
        if (node.children.length > 0) {
          return { ...node, children: addSubClassRecursive(node.children) };
        }
        return node;
      });
    };
    if (nodes) setNodes(addSubClassRecursive(nodes));
    setNodesError(false);
  };

  const deleteNode = (nodeId: number | string) => {
    const deleteNodeRecursive = (nodes: TreeNode[]): TreeNode[] => {
      return nodes
        ?.map((node: TreeNode) => {
          if (node?.children?.length > 0) {
            return { ...node, children: deleteNodeRecursive(node?.children) };
          }
          return node;
        })
        ?.filter((node: TreeNode) => {
          if (node?.id === nodeId) {
            if (node?.children?.length > 0 || node?.fieldName) {
              setCurrentNode(node);
              setIsModalOpen(true);
              return true;
            }
          }
          return !(
            node?.id === nodeId &&
            node?.children?.length === 0 &&
            !node?.fieldName
          );
        });
    };

    if (nodes) setNodes(deleteNodeRecursive(nodes));
  };

  const confirmDeleteNode = () => {
    const deleteNodeRecursive = (nodes: TreeNode[]) => {
      return nodes?.filter((node: TreeNode) => {
        if (currentNode && node.id === currentNode.id) {
          return false;
        }
        if (node.children.length > 0) {
          node.children = deleteNodeRecursive(node.children);
        }
        return true;
      });
    };

    setNodes(deleteNodeRecursive(nodes));
    setIsModalOpen(false);
    setCurrentNode(null);
  };

  return (
    <div>
      <div>
        <Button onClick={addMainClass}>
          {t('datasetGroups.classHierarchy.addClassButton') ?? ''}
        </Button>
        <div>
          {nodes?.map((node) => (
            <ClassHeirarchyTreeNode
              key={node.id}
              node={node}
              onAddSubClass={addSubClass}
              onDelete={deleteNode}
              nodes={nodes}
              setNodesError={setNodesError}
              nodesError={nodesError}
            />
          ))}
        </div>
      </div>
      <Dialog
        isOpen={isModalOpen}
        title={t('datasetGroups.modals.deleteClassTitle') ?? ''}
        footer={
          <div className="footer-button-wrapper">
            <Button
              appearance={ButtonAppearanceTypes.SECONDARY}
              onClick={() => setIsModalOpen(false)}
            >
              {t('global.cancel') ?? ''}
            </Button>
            <Button
              appearance={ButtonAppearanceTypes.ERROR}
              onClick={() => confirmDeleteNode()}
            >
              {t('global.delete') ?? ''}
            </Button>
          </div>
        }
        onClose={() => setIsModalOpen(false)}
      >
        {t('datasetGroups.modals.deleteClaassDesc') ?? ''}
      </Dialog>
    </div>
  );
};

export default ClassHierarchy;
