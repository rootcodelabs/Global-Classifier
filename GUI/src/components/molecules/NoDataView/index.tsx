import React from 'react';
import { MdDashboard } from 'react-icons/md';
import './NoDataView.scss';
interface NoDataViewProps {
  text?: string;
  description?: string;
}

const NoDataView: React.FC<NoDataViewProps> = ({ text, description }) => {
  return (
    <div className="text-center p-5">
      {<MdDashboard size={50} color="grey" />}
      <div className="text-center text-grey text-20">
        {text}
      </div>
      <br/>
      <div className="text-center text-grey text-18">
        {description}
      </div>
    </div>
  );
};

export default NoDataView;
