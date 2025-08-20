import { forwardRef, useState, useEffect, ChangeEvent, KeyboardEvent } from 'react';
import { MdOutlineSearch } from 'react-icons/md';
import { Icon, FormInput } from 'components';
import { DefaultTFuncReturn } from 'i18next';
import './SearchInput.scss';

type SearchInputProps = {
  onSearch: (searchTerm: string) => void;
  placeholder?: string | DefaultTFuncReturn;
  initialValue?: string;
  label?: string;
  disabled?: boolean;
  name?: string;
};

const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(
  (
    { 
      onSearch, 
      placeholder = 'Search...', 
      initialValue = '', 
      label = '', 
      disabled = false,
      name = 'search',
    }, 
    ref
  ) => {
    const [searchTerm, setSearchTerm] = useState(initialValue==="all"?"":initialValue);
    
    // Add useEffect to update internal state when initialValue prop changes
    useEffect(() => {
      setSearchTerm(initialValue==="all"?"":initialValue);
    }, [initialValue]);

    const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
      setSearchTerm(e.target.value);
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        onSearch(searchTerm);
      }
    };

    const handleSearchClick = () => {
      onSearch(searchTerm);
    };

    return (
      <div className="search-input-container">
        <FormInput
          ref={ref}
          label={label}
          hideLabel={!label}
          placeholder={String(placeholder)}
          value={searchTerm}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          name={name}
        >
          <button 
            className="search-button" 
            onClick={handleSearchClick}
            disabled={disabled}
            type="button"
            aria-label="Search"
          >
            <Icon 
              icon={<MdOutlineSearch fontSize={20} />} 
              size="medium" 
              label="Search"
            />
          </button>
        </FormInput>
      </div>
    );
  }
);

export default SearchInput;