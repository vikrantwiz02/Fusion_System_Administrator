import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { MantineProvider } from "@mantine/core";
import "@mantine/core/styles.css";

import { AuthProvider } from "./context/AuthContext.jsx";
import RequireAuth from "./components/RequireAuth/RequireAuth.jsx";

import ArchiveStudentsPage from "./pages/ArchivingPages/ArchiveStudentsPage.jsx";
import ArchiveFacultyPage from "./pages/ArchivingPages/ArchiveFacultyPage.jsx";

import DeleteUserPage from "./pages/UserManagementPages/DeleteUserPage.jsx";
import ResetUserPasswordPage from "./pages/UserManagementPages/ResetUserPasswordPage.jsx";
import StudentCreationPage from "./pages/UserManagementPages/StudentCreationPage.jsx";
import FacultyCreationPage from "./pages/UserManagementPages/FacultyCreationPage.jsx";
import StaffCreationPage from "./pages/UserManagementPages/StaffCreationPage.jsx";

import CreateCustomRolePage from "./pages/RoleManagementPages/CreateCustomRolePage.jsx";
import EditUserRolePage from "./pages/RoleManagementPages/EditUserRolePage.jsx";
import ManageRoleAccessPage from "./pages/RoleManagementPages/ManageRoleAccessPage.jsx";

import UserDirectory from "./pages/UserDirectory/UserDirectory.jsx";
import AuditLogPage from "./pages/AuditLogPage/AuditLogPage.jsx";

import LoginPage from "./pages/Login/LoginPage.jsx";
import Sidebar from "./components/Sidebar/Sidebar.jsx";
import { Notifications } from '@mantine/notifications';

function Layout() {
  return (
    <div style={{ display: "flex", height: "100vh", width: "100vw", overflow: "hidden" }}>
      <Sidebar />
      <div style={{ flex: 1, overflowY: "auto", paddingRight: "80px" }}>
        <Routes>
          <Route
            path="/UserDirectory"
            element={
              <RequireAuth>
                <UserDirectory />
              </RequireAuth>
            }
          />
          <Route
            path="/UserManagement/CreateStudent"
            element={
              <RequireAuth>
                <StudentCreationPage />
              </RequireAuth>
            }
          />
          <Route
            path="/UserManagement/CreateFaculty"
            element={
              <RequireAuth>
                <FacultyCreationPage />
              </RequireAuth>
            }
          />
          <Route
            path="/UserManagement/CreateStaff"
            element={
              <RequireAuth>
                <StaffCreationPage />
              </RequireAuth>
            }
          />
          <Route
            path="/UserManagement/DeleteUser"
            element={
              <RequireAuth>
                <DeleteUserPage />
              </RequireAuth>
            }
          />
          <Route
            path="/UserManagement/ResetUserPassword"
            element={
              <RequireAuth>
                <ResetUserPasswordPage />
              </RequireAuth>
            }
          />
          <Route
            path="/RoleManagement/CreateCustomRole"
            element={
              <RequireAuth>
                <CreateCustomRolePage />
              </RequireAuth>
            }
          />
          <Route
            path="/RoleManagement/EditUserRole"
            element={
              <RequireAuth>
                <EditUserRolePage />
              </RequireAuth>
            }
          />
          <Route
            path="/RoleManagement/ManageRoleAccess"
            element={
              <RequireAuth>
                <ManageRoleAccessPage />
              </RequireAuth>
            }
          />
          <Route
            path="/archive/students"
            element={
              <RequireAuth>
                <ArchiveStudentsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/archive/faculty"
            element={
              <RequireAuth>
                <ArchiveFacultyPage />
              </RequireAuth>
            }
          />
          <Route
            path="/backups"
            element={
              <RequireAuth>
                <BackupPage />
              </RequireAuth>
            }
          />
          <Route
            path="/backups/schedules"
            element={
              <RequireAuth>
                <SchedulePage />
              </RequireAuth>
            }
          />
          <Route path="/UserDirectory" element={<RequireAuth><UserDirectory /></RequireAuth>} />
          <Route path="/UserManagement/CreateStudent" element={<RequireAuth><StudentCreationPage /></RequireAuth>} />
          <Route path="/UserManagement/CreateFaculty" element={<RequireAuth><FacultyCreationPage /></RequireAuth>} />
          <Route path="/UserManagement/CreateStaff" element={<RequireAuth><StaffCreationPage /></RequireAuth>} />
          <Route path="/UserManagement/DeleteUser" element={<RequireAuth><DeleteUserPage /></RequireAuth>} />
          <Route path="/UserManagement/ResetUserPassword" element={<RequireAuth><ResetUserPasswordPage /></RequireAuth>} />
          <Route path="/RoleManagement/CreateCustomRole" element={<RequireAuth><CreateCustomRolePage /></RequireAuth>} />
          <Route path="/RoleManagement/EditUserRole" element={<RequireAuth><EditUserRolePage /></RequireAuth>} />
          <Route path="/RoleManagement/ManageRoleAccess" element={<RequireAuth><ManageRoleAccessPage /></RequireAuth>} />
          <Route path="/archive/students" element={<RequireAuth><ArchiveStudentsPage /></RequireAuth>} />
          <Route path="/archive/faculty" element={<RequireAuth><ArchiveFacultyPage /></RequireAuth>} />
          <Route path="/AuditLog" element={<RequireAuth><AuditLogPage /></RequireAuth>} />
        </Routes>
      </div>
    </div>
  );
}

function App() {
  return (
    <MantineProvider withGlobalStyles withNormalizeCSS>
      <Notifications />
      <AuthProvider>
        <Router>
          <Routes>
            {/* Route to the Login page by default */}
            <Route path="/login" element={<LoginPage />} />

            {/* The default route now redirects to /login */}
            <Route path="/" element={<Navigate to="/login" />} />

            {/* Other protected routes */}
            <Route path="/*" element={<Layout />} />
          </Routes>
        </Router>
      </AuthProvider>
    </MantineProvider>
  );
}

export default App;
