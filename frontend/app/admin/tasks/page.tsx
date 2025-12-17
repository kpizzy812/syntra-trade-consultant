/**
 * Admin Tasks Page
 * Manage social tasks (create, edit, activate/pause, review screenshots)
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api, apiClient } from '@/shared/api/client';
import toast from 'react-hot-toast';

// Types
interface AdminTask {
  id: number;
  title_ru: string;
  title_en: string;
  description_ru: string | null;
  description_en: string | null;
  icon: string;
  task_type: string;
  telegram_channel_id: string | null;
  telegram_channel_url: string | null;
  twitter_target_username: string | null;
  verification_type: string;
  reward_points: number;
  unsubscribe_penalty: number;
  max_completions: number | null;
  current_completions: number;
  is_repeatable: boolean;
  requires_premium: boolean;
  min_level: number;
  priority: number;
  status: string;
  starts_at: string | null;
  expires_at: string | null;
  created_at: string;
}

interface PendingReview {
  completion_id: number;
  task_id: number;
  task_title: string;
  task_icon: string;
  user_id: number;
  username: string | null;
  first_name: string | null;
  screenshot_url: string | null;
  started_at: string;
}

type TabType = 'tasks' | 'pending' | 'create';

// Admin API functions
const adminApi = {
  getTasks: async (): Promise<AdminTask[]> => {
    const response = await apiClient.get('/api/admin/tasks/');
    return response.data;
  },

  createTask: async (data: Partial<AdminTask>): Promise<AdminTask> => {
    const response = await apiClient.post('/api/admin/tasks/', data);
    return response.data;
  },

  updateTask: async (taskId: number, data: Partial<AdminTask>): Promise<AdminTask> => {
    const response = await apiClient.put(`/api/admin/tasks/${taskId}`, data);
    return response.data;
  },

  activateTask: async (taskId: number): Promise<void> => {
    await apiClient.post(`/api/admin/tasks/${taskId}/activate`);
  },

  pauseTask: async (taskId: number): Promise<void> => {
    await apiClient.post(`/api/admin/tasks/${taskId}/pause`);
  },

  getPendingReviews: async (): Promise<PendingReview[]> => {
    const response = await apiClient.get('/api/admin/tasks/pending-reviews');
    return response.data;
  },

  approveCompletion: async (completionId: number, notes?: string): Promise<void> => {
    await apiClient.post(`/api/admin/tasks/completions/${completionId}/approve`, { notes });
  },

  rejectCompletion: async (completionId: number, reason: string): Promise<void> => {
    await apiClient.post(`/api/admin/tasks/completions/${completionId}/reject`, { reason });
  },
};

// Task type options
const TASK_TYPES = [
  { value: 'telegram_subscribe_channel', label: 'Telegram Channel' },
  { value: 'telegram_subscribe_chat', label: 'Telegram Chat' },
  { value: 'twitter_follow', label: 'Twitter Follow' },
];

const VERIFICATION_TYPES = [
  { value: 'auto_telegram', label: 'Auto (Telegram API)' },
  { value: 'manual_screenshot', label: 'Manual (Screenshot)' },
];

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-500/20 text-gray-400',
  active: 'bg-green-500/20 text-green-400',
  paused: 'bg-yellow-500/20 text-yellow-400',
  completed: 'bg-blue-500/20 text-blue-400',
  expired: 'bg-red-500/20 text-red-400',
};

export default function AdminTasksPage() {
  const [activeTab, setActiveTab] = useState<TabType>('tasks');
  const [tasks, setTasks] = useState<AdminTask[]>([]);
  const [pendingReviews, setPendingReviews] = useState<PendingReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingTask, setEditingTask] = useState<AdminTask | null>(null);

  // Form state for create/edit
  const [formData, setFormData] = useState({
    title_ru: '',
    title_en: '',
    description_ru: '',
    description_en: '',
    icon: '✈️',
    task_type: 'telegram_subscribe_channel',
    telegram_channel_id: '',
    telegram_channel_url: '',
    twitter_target_username: '',
    verification_type: 'auto_telegram',
    reward_points: 100,
    unsubscribe_penalty: 50,
    max_completions: '',
    is_repeatable: false,
    requires_premium: false,
    min_level: 1,
    priority: 100,
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [tasksData, reviewsData] = await Promise.all([
        adminApi.getTasks(),
        adminApi.getPendingReviews(),
      ]);
      setTasks(tasksData);
      setPendingReviews(reviewsData);
    } catch (error: any) {
      console.error('Failed to load data:', error);
      if (error?.response?.status === 403) {
        toast.error('Access denied. Admin rights required.');
      } else {
        toast.error('Failed to load data');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreateTask = async () => {
    try {
      const data = {
        ...formData,
        max_completions: formData.max_completions ? parseInt(formData.max_completions) : null,
        telegram_channel_id: formData.telegram_channel_id || null,
        telegram_channel_url: formData.telegram_channel_url || null,
        twitter_target_username: formData.twitter_target_username || null,
        description_ru: formData.description_ru || null,
        description_en: formData.description_en || null,
      };

      await adminApi.createTask(data);
      toast.success('Task created successfully');
      resetForm();
      setActiveTab('tasks');
      loadData();
    } catch (error) {
      console.error('Failed to create task:', error);
      toast.error('Failed to create task');
    }
  };

  const handleUpdateTask = async () => {
    if (!editingTask) return;

    try {
      const data = {
        ...formData,
        max_completions: formData.max_completions ? parseInt(formData.max_completions) : null,
        telegram_channel_id: formData.telegram_channel_id || null,
        telegram_channel_url: formData.telegram_channel_url || null,
        twitter_target_username: formData.twitter_target_username || null,
        description_ru: formData.description_ru || null,
        description_en: formData.description_en || null,
      };

      await adminApi.updateTask(editingTask.id, data);
      toast.success('Task updated successfully');
      setEditingTask(null);
      resetForm();
      setActiveTab('tasks');
      loadData();
    } catch (error) {
      console.error('Failed to update task:', error);
      toast.error('Failed to update task');
    }
  };

  const handleActivateTask = async (taskId: number) => {
    try {
      await adminApi.activateTask(taskId);
      toast.success('Task activated');
      loadData();
    } catch (error) {
      console.error('Failed to activate task:', error);
      toast.error('Failed to activate task');
    }
  };

  const handlePauseTask = async (taskId: number) => {
    try {
      await adminApi.pauseTask(taskId);
      toast.success('Task paused');
      loadData();
    } catch (error) {
      console.error('Failed to pause task:', error);
      toast.error('Failed to pause task');
    }
  };

  const handleApprove = async (completionId: number) => {
    try {
      await adminApi.approveCompletion(completionId);
      toast.success('Completion approved');
      loadData();
    } catch (error) {
      console.error('Failed to approve:', error);
      toast.error('Failed to approve');
    }
  };

  const handleReject = async (completionId: number) => {
    try {
      await adminApi.rejectCompletion(completionId, 'Screenshot rejected by admin');
      toast.success('Completion rejected');
      loadData();
    } catch (error) {
      console.error('Failed to reject:', error);
      toast.error('Failed to reject');
    }
  };

  const startEditTask = (task: AdminTask) => {
    setEditingTask(task);
    setFormData({
      title_ru: task.title_ru,
      title_en: task.title_en,
      description_ru: task.description_ru || '',
      description_en: task.description_en || '',
      icon: task.icon,
      task_type: task.task_type,
      telegram_channel_id: task.telegram_channel_id || '',
      telegram_channel_url: task.telegram_channel_url || '',
      twitter_target_username: task.twitter_target_username || '',
      verification_type: task.verification_type,
      reward_points: task.reward_points,
      unsubscribe_penalty: task.unsubscribe_penalty,
      max_completions: task.max_completions?.toString() || '',
      is_repeatable: task.is_repeatable,
      requires_premium: task.requires_premium,
      min_level: task.min_level,
      priority: task.priority,
    });
    setActiveTab('create');
  };

  const resetForm = () => {
    setFormData({
      title_ru: '',
      title_en: '',
      description_ru: '',
      description_en: '',
      icon: '✈️',
      task_type: 'telegram_subscribe_channel',
      telegram_channel_id: '',
      telegram_channel_url: '',
      twitter_target_username: '',
      verification_type: 'auto_telegram',
      reward_points: 100,
      unsubscribe_penalty: 50,
      max_completions: '',
      is_repeatable: false,
      requires_premium: false,
      min_level: 1,
      priority: 100,
    });
    setEditingTask(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-white p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold mb-2">Task Management</h1>
          <p className="text-gray-400">Create and manage social tasks for users</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => { setActiveTab('tasks'); resetForm(); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === 'tasks'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            All Tasks ({tasks.length})
          </button>
          <button
            onClick={() => { setActiveTab('pending'); resetForm(); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === 'pending'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            Pending Reviews ({pendingReviews.length})
          </button>
          <button
            onClick={() => { setActiveTab('create'); resetForm(); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === 'create'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            + Create Task
          </button>
        </div>

        {/* Tasks List */}
        {activeTab === 'tasks' && (
          <div className="space-y-4">
            {tasks.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                No tasks yet. Create your first task!
              </div>
            ) : (
              tasks.map((task) => (
                <motion.div
                  key={task.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-gray-900 border border-gray-800 rounded-xl p-4"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <span className="text-2xl">{task.icon}</span>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium">{task.title_en}</h3>
                          <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLORS[task.status]}`}>
                            {task.status}
                          </span>
                        </div>
                        <p className="text-sm text-gray-400 mt-1">{task.title_ru}</p>
                        <div className="flex flex-wrap gap-3 mt-2 text-xs text-gray-500">
                          <span>+{task.reward_points} pts</span>
                          <span>-{task.unsubscribe_penalty} penalty</span>
                          <span>{task.current_completions} completions</span>
                          <span>Type: {task.task_type}</span>
                          <span>Verify: {task.verification_type}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2 shrink-0">
                      {task.status === 'active' ? (
                        <button
                          onClick={() => handlePauseTask(task.id)}
                          className="px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded-lg text-sm hover:bg-yellow-500/30"
                        >
                          Pause
                        </button>
                      ) : (
                        <button
                          onClick={() => handleActivateTask(task.id)}
                          className="px-3 py-1.5 bg-green-500/20 text-green-400 rounded-lg text-sm hover:bg-green-500/30"
                        >
                          Activate
                        </button>
                      )}
                      <button
                        onClick={() => startEditTask(task)}
                        className="px-3 py-1.5 bg-blue-500/20 text-blue-400 rounded-lg text-sm hover:bg-blue-500/30"
                      >
                        Edit
                      </button>
                    </div>
                  </div>
                </motion.div>
              ))
            )}
          </div>
        )}

        {/* Pending Reviews */}
        {activeTab === 'pending' && (
          <div className="space-y-4">
            {pendingReviews.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                No pending reviews
              </div>
            ) : (
              pendingReviews.map((review) => (
                <motion.div
                  key={review.completion_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-gray-900 border border-gray-800 rounded-xl p-4"
                >
                  <div className="flex items-start gap-4">
                    {/* Screenshot Preview */}
                    {review.screenshot_url ? (
                      <a
                        href={review.screenshot_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0"
                      >
                        <img
                          src={review.screenshot_url}
                          alt="Screenshot"
                          className="w-32 h-24 object-cover rounded-lg border border-gray-700 hover:border-blue-500 transition"
                        />
                      </a>
                    ) : (
                      <div className="w-32 h-24 bg-gray-800 rounded-lg border border-gray-700 flex items-center justify-center text-gray-500 text-xs shrink-0">
                        No screenshot
                      </div>
                    )}

                    <div className="flex-1">
                      <h3 className="font-medium">{review.task_title}</h3>
                      <div className="text-sm text-gray-400 mt-1">
                        User: {review.first_name} {review.username && `(@${review.username})`}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        Started: {new Date(review.started_at).toLocaleString()}
                      </div>
                    </div>

                    <div className="flex gap-2 shrink-0">
                      <button
                        onClick={() => handleApprove(review.completion_id)}
                        className="px-4 py-2 bg-green-500/20 text-green-400 rounded-lg text-sm font-medium hover:bg-green-500/30"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => handleReject(review.completion_id)}
                        className="px-4 py-2 bg-red-500/20 text-red-400 rounded-lg text-sm font-medium hover:bg-red-500/30"
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                </motion.div>
              ))
            )}
          </div>
        )}

        {/* Create/Edit Form */}
        {activeTab === 'create' && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gray-900 border border-gray-800 rounded-xl p-6"
          >
            <h2 className="text-lg font-bold mb-4">
              {editingTask ? 'Edit Task' : 'Create New Task'}
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Basic Info */}
              <div>
                <label className="block text-sm text-gray-400 mb-1">Title (EN) *</label>
                <input
                  type="text"
                  value={formData.title_en}
                  onChange={(e) => setFormData({ ...formData, title_en: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  placeholder="Subscribe to our channel"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Title (RU) *</label>
                <input
                  type="text"
                  value={formData.title_ru}
                  onChange={(e) => setFormData({ ...formData, title_ru: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  placeholder="Подпишись на канал"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Description (EN)</label>
                <textarea
                  value={formData.description_en}
                  onChange={(e) => setFormData({ ...formData, description_en: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  rows={2}
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Description (RU)</label>
                <textarea
                  value={formData.description_ru}
                  onChange={(e) => setFormData({ ...formData, description_ru: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  rows={2}
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Icon</label>
                <input
                  type="text"
                  value={formData.icon}
                  onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  placeholder="✈️"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Task Type *</label>
                <select
                  value={formData.task_type}
                  onChange={(e) => setFormData({ ...formData, task_type: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                >
                  {TASK_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>{type.label}</option>
                  ))}
                </select>
              </div>

              {/* Telegram Settings */}
              {formData.task_type.includes('telegram') && (
                <>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Channel ID *</label>
                    <input
                      type="text"
                      value={formData.telegram_channel_id}
                      onChange={(e) => setFormData({ ...formData, telegram_channel_id: e.target.value })}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                      placeholder="@syntraai or -1001234567890"
                    />
                  </div>

                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Channel URL</label>
                    <input
                      type="text"
                      value={formData.telegram_channel_url}
                      onChange={(e) => setFormData({ ...formData, telegram_channel_url: e.target.value })}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                      placeholder="https://t.me/syntraai"
                    />
                  </div>
                </>
              )}

              {/* Twitter Settings */}
              {formData.task_type === 'twitter_follow' && (
                <div className="md:col-span-2">
                  <label className="block text-sm text-gray-400 mb-1">Twitter Username *</label>
                  <input
                    type="text"
                    value={formData.twitter_target_username}
                    onChange={(e) => setFormData({ ...formData, twitter_target_username: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                    placeholder="syntraai (without @)"
                  />
                </div>
              )}

              <div>
                <label className="block text-sm text-gray-400 mb-1">Verification Type *</label>
                <select
                  value={formData.verification_type}
                  onChange={(e) => setFormData({ ...formData, verification_type: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                >
                  {VERIFICATION_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>{type.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Reward Points *</label>
                <input
                  type="number"
                  value={formData.reward_points}
                  onChange={(e) => setFormData({ ...formData, reward_points: parseInt(e.target.value) })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  min={1}
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Unsubscribe Penalty</label>
                <input
                  type="number"
                  value={formData.unsubscribe_penalty}
                  onChange={(e) => setFormData({ ...formData, unsubscribe_penalty: parseInt(e.target.value) })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  min={0}
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Max Completions</label>
                <input
                  type="number"
                  value={formData.max_completions}
                  onChange={(e) => setFormData({ ...formData, max_completions: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  placeholder="Leave empty for unlimited"
                  min={1}
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Priority</label>
                <input
                  type="number"
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  min={0}
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Min Level</label>
                <input
                  type="number"
                  value={formData.min_level}
                  onChange={(e) => setFormData({ ...formData, min_level: parseInt(e.target.value) })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  min={1}
                />
              </div>

              {/* Checkboxes */}
              <div className="md:col-span-2 flex gap-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_repeatable}
                    onChange={(e) => setFormData({ ...formData, is_repeatable: e.target.checked })}
                    className="w-4 h-4 rounded bg-gray-800 border-gray-700"
                  />
                  <span className="text-sm">Repeatable</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.requires_premium}
                    onChange={(e) => setFormData({ ...formData, requires_premium: e.target.checked })}
                    className="w-4 h-4 rounded bg-gray-800 border-gray-700"
                  />
                  <span className="text-sm">Requires Premium</span>
                </label>
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-3 mt-6">
              <button
                onClick={editingTask ? handleUpdateTask : handleCreateTask}
                disabled={!formData.title_en || !formData.title_ru}
                className="px-6 py-2 bg-blue-500 text-white rounded-lg font-medium hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {editingTask ? 'Update Task' : 'Create Task'}
              </button>

              {editingTask && (
                <button
                  onClick={resetForm}
                  className="px-6 py-2 bg-gray-700 text-white rounded-lg font-medium hover:bg-gray-600"
                >
                  Cancel
                </button>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
