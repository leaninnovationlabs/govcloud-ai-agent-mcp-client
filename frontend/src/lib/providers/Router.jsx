import React, { lazy } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import App from "@/App"

export const ROUTES = {
    DEFAULT: "/chat",
    DASHBOARD: "/dashboard",
    TEAM: "/team",
    EDIT_PERSONA: "/team/edit",
    CREATE_PERSONA: "/team/create",
    CHAT: "/chat",
    WORKFLOWS: "/workflows",
    CREATE_WORKFLOW: "/workflows/create",
    EDIT_WORKFLOW: "/workflows/edit",
    APPLICATIONS: "/applications",
    CREATE_APPLICATION: "/applications/create", 
    EDIT_APPLICATION: "/applications/edit",
    SETTINGS: "/settings",
    LOGIN: "/login",
    SIGNUP: "/signup",
    PROJECTS: "/projects",
    NEW_PROJECT: "/projects/create"
}

// Minimum delay so the loader doesn't flash at the user
const HomePage = lazy(() => {
    return Promise.all([
        import("@/pages/Home.page"),
        new Promise(resolve => setTimeout(resolve, 1000))
    ])
        .then(([moduleExports]) => moduleExports);
});

const NotFoundPage = lazy(() => import('@/pages/NotFound.page'));

const LoginPage = lazy(() => import('@/pages/public/Login.page'));
const SignupPage = lazy(() => import('@/pages/public/Signup.page'));

const CreateProjectPage = lazy(() => import('@/pages/projects/Create.page'));

const TeamViewPage = lazy(() => import('@/pages/team/View.page'));
const CreatePersonaPage = lazy(() => import('@/pages/team/Create.page'));
const EditPersonaPage = lazy(() => import('@/pages/team/Edit.page'));
const ChatPage = lazy(() => import('@/pages/chat/Chat.page'));

const ApplicationsViewPage = lazy(() => import('@/pages/applications/View.page'));
const CreateApplicationPage = lazy(() => import('@/pages/applications/Create.page'));
const EditApplicationPage = lazy(() => import('@/pages/applications/Edit.page'));

const WorkflowsViewPage = lazy(() => import('@/pages/workflows/View.page'));
const CreateWorkflowPage = lazy(() => import('@/pages/workflows/Create.page'));
const EditWorkflowPage = lazy(() => import('@/pages/workflows/Edit.page'));

const router = createBrowserRouter([
    
    ////////////////////////////////
    ////// Public Routes ////////
    ////////////////////////////////
    {
        path: ROUTES.LOGIN,
        element: <LoginPage />,
    },
    {
        path: ROUTES.SIGNUP,
        element: <SignupPage />,
    },
    ////////////////////////////////
    ////// Protected Routes ////////
    ////////////////////////////////
    {
        path: '/',
        element: <App />,
        errorElement: null, //TODO
        children: [
            {
                index: true,
                element: <HomePage />
            },
            // Team
            {
                path: ROUTES.TEAM,
                element: <TeamViewPage />
            },
            {
                path: ROUTES.CREATE_PERSONA,
                element: <CreatePersonaPage />
            },
            {
                path: ROUTES.EDIT_PERSONA,
                element: <EditPersonaPage />
            },
            // Chat
            {
                path: ROUTES.CHAT,
                element: <ChatPage />
            },
            // Workflows
            {
                path: ROUTES.WORKFLOWS,
                element: <WorkflowsViewPage />
            },
            {
                path: ROUTES.CREATE_WORKFLOW,
                element: <CreateWorkflowPage />
            },
            {
                path: ROUTES.EDIT_WORKFLOW,
                element: <EditWorkflowPage />
            },
            // Applications
            {
                path: ROUTES.APPLICATIONS,
                element: <ApplicationsViewPage />
            },
            {
                path: ROUTES.CREATE_APPLICATION,
                element: <CreateApplicationPage />
            },
            {
                path: ROUTES.EDIT_APPLICATION,
                element: <EditApplicationPage />
            },
            // Projects
            {
                path: ROUTES.PROJECTS,
                element: <HomePage />
            },
            {
                path: ROUTES.NEW_PROJECT,
                element: <CreateProjectPage />
            },
            {
                path: ROUTES.SETTINGS,
                element: <HomePage />
            },
            {
                path: '*',
                element: <NotFoundPage />
            }
        ]
    }
]);

export default function () {
    return <RouterProvider router={router} />
}