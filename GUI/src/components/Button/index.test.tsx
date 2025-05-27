import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Button from './index';

describe('Button Component', () => {
  test('renders with default props', () => {
    render(<Button>Click me</Button>);
    
    const button = screen.getByRole('button', { name: 'Click me' });
    expect(button).toBeInTheDocument();
    expect(button).toHaveClass('btn');
    expect(button).toHaveClass('btn--primary'); // default appearance
    expect(button).toHaveClass('btn--m'); // default size
  });

  test('applies correct appearance classes', () => {
    const { rerender } = render(<Button appearance="secondary">Secondary</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn--secondary');

    rerender(<Button appearance="text">Text</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn--text');

    rerender(<Button appearance="icon">Icon</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn--icon');

    rerender(<Button appearance="error">Error</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn--error');

    rerender(<Button appearance="success">Success</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn--success');
  });

  test('applies correct size classes', () => {
    const { rerender } = render(<Button size="m">Medium</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn--m');

    rerender(<Button size="s">Small</Button>);
    expect(screen.getByRole('button')).toHaveClass('btn--s');
  });

  test('handles disabled state correctly', () => {
    render(<Button disabled>Disabled</Button>);
    
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
    expect(button).toHaveClass('btn--disabled');
  });

  test('handles disabledWithoutStyle prop', () => {
    render(<Button disabledWithoutStyle>Disabled Without Style</Button>);
    
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
    expect(button).not.toHaveClass('btn--disabled');
  });

  test('renders children correctly', () => {
    render(
      <Button>
        <span data-testid="child">Child Element</span>
      </Button>
    );
    
    expect(screen.getByTestId('child')).toBeInTheDocument();
    expect(screen.getByTestId('child')).toHaveTextContent('Child Element');
  });

  test('shows loading spinner when showLoadingIcon is true', () => {
    render(<Button showLoadingIcon>Loading</Button>);
    
    const spinner = screen.getByRole('button').querySelector('.spinner');
    expect(spinner).toBeInTheDocument();
    expect(spinner).toHaveClass('spinner');
  });

  test('passes additional props to button element', async () => {
    const handleClick = jest.fn();
    render(
      <Button onClick={handleClick} data-testid="custom-button">
        Click Me
      </Button>
    );
    
    const button = screen.getByTestId('custom-button');
    expect(button).toBeInTheDocument();
    
    await userEvent.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});