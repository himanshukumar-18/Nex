import { useDispatch, useSelector } from 'react-redux';

/**
 * Pre-typed hooks for standard React-Redux usage throughout the app.
 */
export const useAppDispatch = () => useDispatch();
export const useAppSelector = useSelector;

