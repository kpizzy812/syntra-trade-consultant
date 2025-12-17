/**
 * Chat Message Component
 * Отображает одно сообщение в чате с markdown и syntax highlighting
 * Дизайн в стиле Apple/OpenAI/Anthropic
 */

'use client';

import { useState, useMemo } from 'react';
import Image from 'next/image';
import DOMPurify from 'dompurify';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { vibrate } from '@/shared/telegram/vibration';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  image?: string;  // Base64 image data
  isStreaming?: boolean;
  timestamp?: string;
  onRegenerate?: () => void;
}

/**
 * 🔒 SECURITY: Проверяет URL на безопасность
 * Блокирует javascript:, data:, vbscript: и другие потенциально опасные схемы
 */
function isSafeUrl(url: string | undefined): boolean {
  if (!url) return false;

  const trimmedUrl = url.trim().toLowerCase();

  // Список опасных URL схем
  const dangerousSchemes = [
    'javascript:',
    'data:',
    'vbscript:',
    'file:',
    'about:',
  ];

  // Проверяем на опасные схемы
  const isDangerous = dangerousSchemes.some(scheme =>
    trimmedUrl.startsWith(scheme)
  );

  if (isDangerous) {
    console.warn('[Security] Blocked potentially dangerous URL:', url);
    return false;
  }

  // Разрешаем http(s):, mailto:, tel:, и относительные URLs
  return (
    trimmedUrl.startsWith('http://') ||
    trimmedUrl.startsWith('https://') ||
    trimmedUrl.startsWith('mailto:') ||
    trimmedUrl.startsWith('tel:') ||
    trimmedUrl.startsWith('/') ||
    trimmedUrl.startsWith('#')
  );
}

/**
 * 🔒 SECURITY: Санитизирует текстовый контент
 * Удаляет потенциально опасный HTML и скрипты
 */
function sanitizeText(text: string): string {
  // Для простого текста достаточно экранировать HTML
  // DOMPurify.sanitize с ALLOWED_TAGS: [] полностью удаляет все теги
  return DOMPurify.sanitize(text, {
    ALLOWED_TAGS: [], // Не разрешаем никакие HTML теги
    ALLOWED_ATTR: [], // Не разрешаем никакие атрибуты
  });
}

/**
 * 🔒 SECURITY: Санитизирует HTML контент от ассистента
 * Разрешает только безопасные Telegram HTML теги
 */
function sanitizeAssistantHtml(text: string): string {
  return DOMPurify.sanitize(text, {
    ALLOWED_TAGS: ['b', 'i', 'u', 's', 'code', 'pre', 'blockquote', 'a', 'br', 'p', 'strong', 'em'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
    ALLOW_DATA_ATTR: false,
  });
}

export default function ChatMessage({
  role,
  content,
  image,
  isStreaming = false,
  timestamp,
  onRegenerate,
}: ChatMessageProps) {
  const [showActions, setShowActions] = useState(false);
  const [copied, setCopied] = useState(false);

  // 🔒 SECURITY: Санитизируем контент (на случай если бэкенд скомпрометирован)
  const sanitizedContent = useMemo(() => {
    if (role === 'user') {
      return sanitizeText(content);
    }
    // Assistant content: разрешаем только безопасные HTML теги (Telegram format)
    return sanitizeAssistantHtml(content);
  }, [role, content]);

  const handleCopy = () => {
    vibrate('light');
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRegenerate = () => {
    vibrate('medium');
    onRegenerate?.();
  };

  const isUser = role === 'user';

  return (
    <div
      className={`flex gap-2.5 mb-3 ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      {/* Avatar (только для ассистента) */}
      {!isUser && (
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-black flex items-center justify-center overflow-hidden ring-1 ring-blue-500/30">
          <Image
            src="/syntra/aiminiature.png"
            width={28}
            height={28}
            alt="Syntra AI"
            className="rounded-full"
          />
        </div>
      )}

      {/* Message Content */}
      <div className={`${isUser ? 'max-w-[70%]' : 'max-w-[85%]'}`}>
        <div
          className={`rounded-2xl px-4 py-2.5 ${
            isUser
              ? 'bg-gradient-to-br from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-600/30'
              : 'bg-gradient-to-br from-blue-500/10 via-blue-600/5 to-blue-700/10 backdrop-blur-xl text-gray-100 border border-blue-500/20 shadow-lg shadow-blue-500/10'
          }`}
        >
          {isUser ? (
            // User message - текст и/или изображение
            <>
              {image && (
                <img
                  src={image}
                  alt="Attached"
                  className="mb-2 rounded-lg max-w-full max-h-64 object-contain"
                />
              )}
              {content && (
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {sanitizedContent}
                </p>
              )}
            </>
          ) : (
            // Assistant message - markdown с подсветкой кода (ChatGPT-style)
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
                components={{
                  // Кастомный рендеринг для code blocks
                  code(props: any) {
                    const { node, inline, className, children, ...rest } = props;
                    const match = /language-(\w+)/.exec(className || '');
                    return !inline && match ? (
                      <SyntaxHighlighter
                        style={oneDark}
                        language={match[1]}
                        PreTag="div"
                        className="rounded-xl !mt-3 !mb-3 text-xs"
                        customStyle={{
                          padding: '1rem',
                          borderRadius: '0.75rem',
                          fontSize: '0.8rem',
                        }}
                        {...rest}
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    ) : (
                      <code
                        className="bg-gray-700/50 px-1.5 py-0.5 rounded text-blue-300 text-xs font-mono"
                        {...rest}
                      >
                        {children}
                      </code>
                    );
                  },
                  // Кастомные стили для параграфов
                  p: ({ children, node }) => {
                    // Detect callout blocks (paragraphs starting with emoji)
                    const firstChild = node?.children?.[0];
                    const textContent = (firstChild && 'value' in firstChild) ? firstChild.value : '';
                    const firstChar = typeof textContent === 'string' ? textContent.charAt(0) : '';

                    // Warning/Info callouts (⚠️, 🔥, 💡, ℹ️, ✅, ❌)
                    const isCallout = /^[⚠️🔥💡ℹ️✅❌🎯📊🚨⭐]/.test(firstChar);

                    if (isCallout) {
                      let bgColor = 'bg-yellow-900/20';
                      let borderColor = 'border-yellow-600/50';
                      let textColor = 'text-yellow-200';

                      if (firstChar === '🔥') {
                        bgColor = 'bg-orange-900/20';
                        borderColor = 'border-orange-600/50';
                        textColor = 'text-orange-200';
                      } else if (firstChar === '💡' || firstChar === 'ℹ️') {
                        bgColor = 'bg-blue-900/20';
                        borderColor = 'border-blue-600/50';
                        textColor = 'text-blue-200';
                      } else if (firstChar === '✅') {
                        bgColor = 'bg-green-900/20';
                        borderColor = 'border-green-600/50';
                        textColor = 'text-green-200';
                      } else if (firstChar === '❌' || firstChar === '🚨') {
                        bgColor = 'bg-red-900/20';
                        borderColor = 'border-red-600/50';
                        textColor = 'text-red-200';
                      }

                      return (
                        <div className={`${bgColor} ${borderColor} ${textColor} border-l-4 rounded-r-lg px-4 py-3 mb-3 mt-3`}>
                          <p className="text-sm leading-relaxed m-0">
                            {children}
                          </p>
                        </div>
                      );
                    }

                    return (
                      <p className="mb-3 last:mb-0 text-sm leading-relaxed text-gray-200">
                        {children}
                      </p>
                    );
                  },
                  ul: ({ children }) => (
                    <ul className="list-none mb-3 space-y-2 text-sm pl-0">
                      {children}
                    </ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal mb-3 space-y-2 text-sm pl-6">
                      {children}
                    </ol>
                  ),
                  li: ({ children, node }) => {
                    const isOrdered = node?.position ? true : false;
                    return (
                      <li className="text-gray-200 leading-relaxed">
                        {!isOrdered && <span className="text-blue-400 mr-2">•</span>}
                        {children}
                      </li>
                    );
                  },
                  strong: ({ children }) => (
                    <strong className="font-semibold text-white">{children}</strong>
                  ),
                  em: ({ children }) => (
                    <em className="italic text-gray-300">{children}</em>
                  ),
                  a: ({ href, children }) => {
                    // 🔒 SECURITY: Проверяем URL перед рендером
                    if (!isSafeUrl(href)) {
                      return (
                        <span className="text-red-400 line-through" title="Blocked: Unsafe URL">
                          {children}
                        </span>
                      );
                    }
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:text-blue-300 underline underline-offset-2"
                      >
                        {children}
                      </a>
                    );
                  },
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-4 border-gray-600 bg-gray-800/30 pl-4 pr-4 py-2 italic text-gray-300 my-3 rounded-r">
                      {children}
                    </blockquote>
                  ),
                  h1: ({ children }) => (
                    <h1 className="text-xl font-bold mb-3 mt-4 text-white first:mt-0">
                      {children}
                    </h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-lg font-bold mb-3 mt-4 text-white first:mt-0">
                      {children}
                    </h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-base font-semibold mb-2 mt-3 text-white first:mt-0">
                      {children}
                    </h3>
                  ),
                  h4: ({ children }) => (
                    <h4 className="text-sm font-semibold mb-2 mt-3 text-gray-200 first:mt-0">
                      {children}
                    </h4>
                  ),
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-3">
                      <table className="min-w-full divide-y divide-gray-700 border border-gray-700 rounded-lg">
                        {children}
                      </table>
                    </div>
                  ),
                  th: ({ children }) => (
                    <th className="px-4 py-2 text-left text-xs font-semibold text-gray-200 bg-gray-800/50">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="px-4 py-2 text-xs text-gray-300 border-t border-gray-700/50">
                      {children}
                    </td>
                  ),
                  hr: () => (
                    <hr className="border-t border-gray-700 my-4" />
                  ),
                }}
              >
                {sanitizedContent}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Timestamp */}
        {timestamp && (
          <div
            className={`text-xs text-gray-500 mt-1 px-2 ${
              isUser ? 'text-right' : 'text-left'
            }`}
          >
            {new Date(timestamp).toLocaleTimeString('en-US', {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </div>
        )}

      </div>
    </div>
  );
}
