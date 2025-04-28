import { rankItem } from '@tanstack/match-sorter-utils';
import { FilterFn } from '@tanstack/react-table';
import moment from 'moment';

type FormattedOption = {
  label: string;
  value: string;
};

// convert flat array to label, value pairs 
export const formattedArray = (data: string[]|undefined): FormattedOption[]|undefined => {
  return data?.map((name) => ({
    label: name,
    value: name,
  }));
};


export const convertTimestampToDateTime = (timestamp: number) => {
  return moment.unix(timestamp).format('YYYY-MM-DD HH:mm:ss');
};

// determines version numbers for filter
export const parseVersionString = (version: string) => {
  const parts = version.split('.');

  return {
    major: parts[0] !== 'x' ? parseInt(parts[0], 10) : -1,
    minor: parts[1] !== 'x' ? parseInt(parts[1], 10) : -1,
    patch: parts[2] !== 'x' ? parseInt(parts[2], 10) : -1,
  };
};

export const fuzzyFilter: FilterFn<any> = (row, columnId, value, addMeta) => {
  const itemRank = rankItem(row.getValue(columnId), value);
  addMeta({
    itemRank,
  });
  return itemRank.passed;
};

export const formatDate = (date: Date, format: string) => {
  return moment(date).format(format);
};

export const formatDateTime = (date: string) => {
  const momentDate = moment(date);
  const formattedDate = momentDate.format('DD/MM/YYYY');
  const formattedTime = momentDate.format('h.mm A');

  return {
    formattedDate,
    formattedTime,
  };
};

export const formatClassHierarchyArray = (array: string | string[]) => {
  let formattedArray: string[];
  if (typeof array === 'string') {
    try {
      const cleanedInput = array.trim();
      formattedArray = JSON.parse(cleanedInput);
    } catch (error) {
      console.error('Error parsing input string:', error);
      return '';
    }
  } else {
    formattedArray = array;
  }

  return formattedArray
    .map((item, index) =>
      index === formattedArray?.length - 1 ? item : item + ' ->'
    )
    .join(' ');
};