import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../layouts/MainLayout.vue'
import { useCurrentStaff } from '../composables/useCurrentStaff'

const page = (title) => ({ component: () => import('../views/Placeholderview.vue'), meta: { title } })

const routes = [
  {
    path: '/login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', component: () => import('../views/Dashboardview.vue') },
      { path: 'clients', component: () => import('../views/ClientsView.vue') },
      { path: 'tasks', component: () => import('../views/Tasksview.vue') },
      {
        path: 'staff',
        component: () => import('../views/StaffView.vue'),
        meta: { requiresHigh: true },
      },
      { path: 'messages', ...page('Communication Log') },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to, from, next) => {
  const { currentUser, authChecked, checkAuth, isHigh } = useCurrentStaff()

  if (!authChecked.value) {
    await checkAuth()
  }

  if (to.path === '/login') {
    if (currentUser.value) {
      return next('/dashboard')
    }
    return next()
  }

  if (!currentUser.value) {
    return next('/login')
  }

  // Prevent accessing Staff Management if effective permissions are not HIGH
  if (to.matched.some((record) => record.meta?.requiresHigh) && !isHigh.value) {
    return next('/dashboard')
  }

  next()
})

export default router
