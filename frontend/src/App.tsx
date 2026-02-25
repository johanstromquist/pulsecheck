import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import ServiceDetail from "./pages/ServiceDetail";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/services/:id" element={<ServiceDetail />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
