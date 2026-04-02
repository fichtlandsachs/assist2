import { RouterProvider } from 'react-router';
import { router } from './routes';
import '../styles/theme.css';
import '../styles/fonts.css';

function App() {
  return <RouterProvider router={router} />;
}

export default App;
