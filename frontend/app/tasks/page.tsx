/**
 * Tasks Page
 * Earn $SYNTRA points by completing social tasks
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '@/shared/api/client';
import Header from '@/components/layout/Header';
import TabBar from '@/components/layout/TabBar';
import DesktopLayout from '@/components/layout/DesktopLayout';
import toast from 'react-hot-toast';
import { useTranslations } from 'next-intl';
import { usePointsStore } from '@/shared/store/pointsStore';

// Helper function to refresh points balance
const refreshPointsBalance = async () => {
  try {
    const data = await api.points.getBalance();
    usePointsStore.getState().setBalance(data);
  } catch (error) {
    console.error('Failed to refresh points balance:', error);
  }
};

interface Task {
  id: number;
  title: string;
  description: string | null;
  icon: string;
  task_type: string;
  reward_points: number;
  unsubscribe_penalty: number;
  verification_type: string;
  is_repeatable: boolean;
  requires_premium: boolean;
  telegram_channel_id: string | null;
  telegram_channel_url: string | null;
  twitter_target_username: string | null;
  completion_status: string | null;
  points_awarded: number;
  completed_at: string | null;
}

type TaskStatus = 'idle' | 'starting' | 'verifying' | 'completed' | 'failed';

export default function TasksPage() {
  const t = useTranslations('tasks');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [taskStatuses, setTaskStatuses] = useState<Record<number, TaskStatus>>({});

  // Screenshot upload state
  const [screenshotTask, setScreenshotTask] = useState<Task | null>(null);
  const [uploadingScreenshot, setUploadingScreenshot] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadTasks = useCallback(async () => {
    try {
      const data = await api.tasks.getAvailable(true);
      setTasks(data);
    } catch (error) {
      console.error('Failed to load tasks:', error);
      toast.error(t('load_error'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const handleStartTask = async (task: Task) => {
    // If Telegram task - open channel first
    if (task.telegram_channel_url && task.task_type.includes('telegram')) {
      window.open(task.telegram_channel_url, '_blank');
    }

    // If Twitter task - open Twitter profile
    if (task.twitter_target_username && task.task_type === 'twitter_follow') {
      window.open(`https://twitter.com/${task.twitter_target_username}`, '_blank');
    }

    setTaskStatuses(prev => ({ ...prev, [task.id]: 'starting' }));

    try {
      await api.tasks.startTask(task.id);

      // Wait a moment for user to complete action
      setTimeout(() => {
        setTaskStatuses(prev => ({ ...prev, [task.id]: 'idle' }));
        loadTasks();
      }, 2000);

      toast.success(t('task_started'));
    } catch (error: any) {
      console.error('Failed to start task:', error);
      toast.error(error?.response?.data?.detail || t('start_error'));
      setTaskStatuses(prev => ({ ...prev, [task.id]: 'idle' }));
    }
  };

  const handleVerifyTask = async (task: Task) => {
    // For Twitter tasks, open screenshot modal directly
    if (task.task_type === 'twitter_follow' || task.verification_type === 'screenshot') {
      setScreenshotTask(task);
      return;
    }

    setTaskStatuses(prev => ({ ...prev, [task.id]: 'verifying' }));

    try {
      const result = await api.tasks.verifyTask(task.id);

      if (result.success) {
        setTaskStatuses(prev => ({ ...prev, [task.id]: 'completed' }));
        toast.success(`+${result.points_awarded} $SYNTRA!`);
        refreshPointsBalance();
        loadTasks();
      } else if (result.screenshot_required) {
        // Need screenshot for verification
        setTaskStatuses(prev => ({ ...prev, [task.id]: 'idle' }));
        setScreenshotTask(task);
      } else {
        setTaskStatuses(prev => ({ ...prev, [task.id]: 'failed' }));
        toast.error(result.message || t('verify_failed'));

        // Reset after delay
        setTimeout(() => {
          setTaskStatuses(prev => ({ ...prev, [task.id]: 'idle' }));
        }, 3000);
      }
    } catch (error: any) {
      console.error('Failed to verify task:', error);
      setTaskStatuses(prev => ({ ...prev, [task.id]: 'failed' }));
      toast.error(error?.response?.data?.detail || t('verify_error'));

      // Reset after delay
      setTimeout(() => {
        setTaskStatuses(prev => ({ ...prev, [task.id]: 'idle' }));
      }, 3000);
    }
  };

  // Handle screenshot file selection
  const handleScreenshotSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !screenshotTask) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      toast.error(t('invalid_image'));
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast.error(t('image_too_large'));
      return;
    }

    setUploadingScreenshot(true);

    try {
      // Convert to base64 for upload
      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const base64 = reader.result as string;

          // Submit screenshot
          const result = await api.tasks.submitScreenshot(screenshotTask.id, base64);

          if (result.success) {
            toast.success(t('screenshot_submitted'));
            setScreenshotTask(null);
            loadTasks();
          } else {
            toast.error(result.message || t('screenshot_error'));
          }
        } catch (error: any) {
          console.error('Failed to submit screenshot:', error);
          toast.error(error?.response?.data?.detail || t('screenshot_error'));
        } finally {
          setUploadingScreenshot(false);
        }
      };
      reader.readAsDataURL(file);
    } catch (error) {
      console.error('Failed to read file:', error);
      toast.error(t('screenshot_error'));
      setUploadingScreenshot(false);
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const getTaskTypeIcon = (taskType: string): string | null => {
    if (taskType.includes('telegram')) return '/telegram.svg';
    if (taskType.includes('twitter')) return '/x.png';
    return null;
  };

  const getTaskTypeEmoji = (taskType: string) => {
    if (taskType.includes('telegram')) return '✈️';
    if (taskType.includes('twitter')) return '🐦';
    return '📋';
  };

  const getStatusBadge = (task: Task) => {
    const status = task.completion_status;
    if (!status) return null;

    const badges: Record<string, { bg: string; text: string; label: string }> = {
      completed: { bg: 'bg-green-500/20', text: 'text-green-400', label: t('status_completed') },
      pending: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: t('status_pending') },
      pending_review: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: t('status_review') },
      verified: { bg: 'bg-green-500/20', text: 'text-green-400', label: t('status_verified') },
      failed: { bg: 'bg-red-500/20', text: 'text-red-400', label: t('status_failed') },
      revoked: { bg: 'bg-red-500/20', text: 'text-red-400', label: t('status_revoked') },
    };

    const badge = badges[status] || badges.pending;

    return (
      <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${badge.bg} ${badge.text}`}>
        {badge.label}
      </span>
    );
  };

  const renderTaskButton = (task: Task) => {
    const status = taskStatuses[task.id] || 'idle';
    const isCompleted = task.completion_status === 'completed';
    const isPending = task.completion_status === 'pending';
    const isPendingReview = task.completion_status === 'pending_review';

    // Already completed
    if (isCompleted) {
      return (
        <div className="flex items-center gap-1.5 text-green-400 text-xs">
          <span>✓</span>
          <img src="/syntra/$SYNTRA.png" alt="" className="w-4 h-4" />
          <span>+{task.points_awarded}</span>
        </div>
      );
    }

    // Pending review (manual verification)
    if (isPendingReview) {
      return (
        <span className="text-blue-400 text-xs">{t('awaiting_review')}</span>
      );
    }

    // Pending - show verify button
    if (isPending) {
      return (
        <button
          onClick={() => handleVerifyTask(task)}
          disabled={status === 'verifying'}
          className={`
            px-4 py-2 rounded-lg text-xs font-medium transition-all
            ${status === 'verifying'
              ? 'bg-blue-500/50 text-white/70 cursor-wait'
              : 'bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:from-blue-400 hover:to-blue-500 active:scale-95'
            }
          `}
        >
          {status === 'verifying' ? (
            <span className="flex items-center gap-1.5">
              <span className="animate-spin">⟳</span>
              {t('verifying')}
            </span>
          ) : (
            t('verify')
          )}
        </button>
      );
    }

    // Not started - show start button
    return (
      <button
        onClick={() => handleStartTask(task)}
        disabled={status === 'starting'}
        className={`
          px-4 py-2 rounded-lg text-xs font-medium transition-all
          ${status === 'starting'
            ? 'bg-green-500/50 text-white/70 cursor-wait'
            : 'bg-gradient-to-r from-green-500 to-emerald-600 text-white hover:from-green-400 hover:to-emerald-500 active:scale-95'
          }
        `}
      >
        {status === 'starting' ? t('opening') : t('start')}
      </button>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  const availableTasks = tasks.filter(t => t.completion_status !== 'completed');
  const completedTasks = tasks.filter(t => t.completion_status === 'completed');

  return (
    <DesktopLayout>
      <div className="bg-black flex flex-col h-full">
        <Header title={t('title')} showBack={false} />

        <main className="flex-1 overflow-y-auto px-4 pt-4 pb-24 lg:max-w-[1200px] lg:mx-auto lg:w-full">
          <div className="max-w-2xl mx-auto space-y-4">

            {/* Header Card */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-gradient-to-br from-purple-500/10 via-blue-600/5 to-purple-700/10 backdrop-blur-xl border border-purple-500/20 rounded-2xl p-4 shadow-lg"
            >
              <div className="flex items-center gap-3">
                <img
                  src="/syntra/$SYNTRA.png"
                  alt="$SYNTRA"
                  className="w-12 h-12 object-contain"
                />
                <div>
                  <h2 className="text-white font-bold text-lg">{t('earn_points')}</h2>
                  <p className="text-gray-400 text-xs">{t('subtitle')}</p>
                </div>
              </div>
            </motion.div>

            {/* Available Tasks */}
            {availableTasks.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="space-y-3"
              >
                <h3 className="text-white font-bold text-sm px-1">{t('available_tasks')}</h3>

                <AnimatePresence>
                  {availableTasks.map((task, index) => {
                    const iconPath = getTaskTypeIcon(task.task_type);
                    return (
                      <motion.div
                        key={task.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                        transition={{ delay: index * 0.05 }}
                        className="bg-gradient-to-br from-blue-500/10 to-blue-700/10 backdrop-blur-xl border border-blue-500/20 rounded-xl p-4 shadow-lg"
                      >
                        {/* Header: Icon + Title */}
                        <div className="flex items-center gap-3 mb-3">
                          {/* Icon - SVG has priority for telegram/twitter */}
                          <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center shrink-0">
                            {iconPath ? (
                              <img src={iconPath} alt="" className="w-5 h-5" />
                            ) : task.icon ? (
                              <span className="text-xl">{task.icon}</span>
                            ) : (
                              <span className="text-xl">{getTaskTypeEmoji(task.task_type)}</span>
                            )}
                          </div>

                          {/* Title - full width */}
                          <div className="flex-1">
                            <h4 className="text-white font-medium text-sm leading-snug">{task.title}</h4>
                            {getStatusBadge(task) && (
                              <div className="mt-1">{getStatusBadge(task)}</div>
                            )}
                          </div>
                        </div>

                        {/* Description */}
                        {task.description && (
                          <p className="text-gray-400 text-xs mb-3 line-clamp-2">{task.description}</p>
                        )}

                        {/* Footer: Reward info + Button */}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            {/* Reward */}
                            <div className="flex items-center gap-1.5">
                              <img src="/syntra/$SYNTRA.png" alt="" className="w-4 h-4" />
                              <span className="text-green-400 text-xs font-bold">+{task.reward_points}</span>
                            </div>

                            {/* Penalty warning */}
                            {task.unsubscribe_penalty > 0 && (
                              <div className="flex items-center gap-1" title={t('penalty_warning')}>
                                <span className="text-red-400/60 text-[10px]">-{task.unsubscribe_penalty}</span>
                                <span className="text-gray-600 text-[10px]">{t('if_unsub')}</span>
                              </div>
                            )}

                            {/* Premium badge */}
                            {task.requires_premium && (
                              <span className="text-[10px] bg-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded">
                                Premium
                              </span>
                            )}
                          </div>

                          {/* Action Button */}
                          <div className="shrink-0">
                            {renderTaskButton(task)}
                          </div>
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              </motion.div>
            )}

            {/* Empty State */}
            {availableTasks.length === 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-gradient-to-br from-gray-500/10 to-gray-700/10 backdrop-blur-xl border border-gray-500/20 rounded-2xl p-8 text-center"
              >
                <span className="text-4xl mb-3 block">🎉</span>
                <h3 className="text-white font-bold mb-1">{t('all_done')}</h3>
                <p className="text-gray-400 text-sm">{t('check_back')}</p>
              </motion.div>
            )}

            {/* Completed Tasks */}
            {completedTasks.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="space-y-3"
              >
                <h3 className="text-gray-400 font-medium text-sm px-1">{t('completed_tasks')}</h3>

                {completedTasks.map((task) => {
                  const iconPath = getTaskTypeIcon(task.task_type);
                  return (
                    <div
                      key={task.id}
                      className="bg-gradient-to-br from-green-500/5 to-emerald-700/5 backdrop-blur-xl border border-green-500/10 rounded-xl p-4 opacity-60"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-green-500/20 flex items-center justify-center shrink-0">
                          {iconPath ? (
                            <img src={iconPath} alt="" className="w-5 h-5 opacity-70" />
                          ) : task.icon ? (
                            <span className="text-xl">{task.icon}</span>
                          ) : (
                            <span className="text-xl">{getTaskTypeEmoji(task.task_type)}</span>
                          )}
                        </div>
                        <div className="flex-1">
                          <h4 className="text-white font-medium text-sm">{task.title}</h4>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <img src="/syntra/$SYNTRA.png" alt="" className="w-3.5 h-3.5" />
                            <span className="text-green-400 text-xs">+{task.points_awarded}</span>
                          </div>
                        </div>
                        <span className="text-green-400 text-lg shrink-0">✓</span>
                      </div>
                    </div>
                  );
                })}
              </motion.div>
            )}

            {/* Info Card */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="bg-gradient-to-br from-yellow-500/10 to-orange-500/10 backdrop-blur-xl border border-yellow-500/20 rounded-2xl p-4 shadow-lg"
            >
              <h3 className="text-white font-bold text-sm mb-2 flex items-center gap-1.5">
                ⚠️ {t('important')}
              </h3>
              <ul className="space-y-1.5 text-xs text-gray-300">
                <li className="flex items-start gap-2">
                  <span className="text-yellow-400 mt-0.5">•</span>
                  <span>{t('rule_stay_subscribed')}</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-yellow-400 mt-0.5">•</span>
                  <span>{t('rule_penalty')}</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-yellow-400 mt-0.5">•</span>
                  <span>{t('rule_verify')}</span>
                </li>
              </ul>
            </motion.div>
          </div>
        </main>

        <TabBar />

        {/* Screenshot Upload Modal */}
        <AnimatePresence>
          {screenshotTask && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
              onClick={() => !uploadingScreenshot && setScreenshotTask(null)}
            >
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.9, opacity: 0 }}
                onClick={(e) => e.stopPropagation()}
                className="bg-gradient-to-br from-gray-900 to-gray-800 border border-gray-700 rounded-2xl p-6 max-w-sm w-full"
              >
                <div className="text-center mb-4">
                  <div className="w-16 h-16 mx-auto mb-3 rounded-full bg-blue-500/20 flex items-center justify-center">
                    <img src="/x.png" alt="X" className="w-8 h-8" />
                  </div>
                  <h3 className="text-white font-bold text-lg mb-1">{t('upload_screenshot')}</h3>
                  <p className="text-gray-400 text-sm">{t('screenshot_instruction')}</p>
                </div>

                <div className="space-y-3">
                  <div className="bg-gray-800/50 rounded-xl p-4 text-center border-2 border-dashed border-gray-600">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      onChange={handleScreenshotSelect}
                      className="hidden"
                      id="screenshot-input"
                      disabled={uploadingScreenshot}
                    />
                    <label
                      htmlFor="screenshot-input"
                      className={`cursor-pointer block ${uploadingScreenshot ? 'opacity-50' : ''}`}
                    >
                      {uploadingScreenshot ? (
                        <div className="flex flex-col items-center gap-2">
                          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                          <span className="text-gray-400 text-sm">{t('uploading')}</span>
                        </div>
                      ) : (
                        <>
                          <span className="text-3xl mb-2 block">📸</span>
                          <span className="text-blue-400 font-medium">{t('tap_to_upload')}</span>
                          <span className="text-gray-500 text-xs block mt-1">PNG, JPG {t('up_to')} 5MB</span>
                        </>
                      )}
                    </label>
                  </div>

                  <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-3">
                    <p className="text-yellow-400 text-xs">
                      {t('screenshot_hint')}
                    </p>
                  </div>

                  <button
                    onClick={() => setScreenshotTask(null)}
                    disabled={uploadingScreenshot}
                    className="w-full py-3 rounded-xl bg-gray-700 text-white font-medium hover:bg-gray-600 transition-colors disabled:opacity-50"
                  >
                    {t('cancel')}
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </DesktopLayout>
  );
}
