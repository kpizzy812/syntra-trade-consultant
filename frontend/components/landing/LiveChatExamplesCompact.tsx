/**
 * Compact Live Chat Examples - для hero section
 * Компактная версия carousel для размещения справа в hero
 */

'use client';

import { useState } from 'react';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useCurrentLocale } from '@/shared/hooks/useCurrentLocale';

interface ChatExample {
  id: number;
  title: string;
  messages: {
    role: 'user' | 'assistant';
    content: string;
  }[];
}

// Компактные примеры для hero - RU
const CHAT_EXAMPLES_RU: ChatExample[] = [
  {
    id: 1,
    title: 'Технический анализ BTC',
    messages: [
      {
        role: 'user',
        content: 'Дай полный технический анализ BTC прямо сейчас',
      },
      {
        role: 'assistant',
        content: `# Bitcoin Технический Анализ

**Текущая цена:** $43,250
**24h изменение:** +3.2% 📈

## Технические индикаторы
\`\`\`
RSI (14):        62 → Нейтрально-бычий
MACD:           Бычий кроссовер ✅
MA(50):         $41,800 → Поддержка
MA(200):        $38,500 → Долгосрочный тренд
Объем:          Выше среднего (+18%)
\`\`\`

## Ключевые уровни
**Сопротивление:**
• $44,500 - сильный уровень
• $46,000 - психологический барьер
• $48,000 - локальный максимум

**Поддержка:**
• $42,000 - краткосрочная
• $40,500 - важная зона
• $38,000 - критическая поддержка

## Вывод
BTC показывает **бычью структуру** на 4H таймфрейме. Пробой $44,500 может дать движение к $46-48k. Если цена откатит к $42k — это может быть хорошая точка входа.

⚠️ **Риски:** Если пробьем $40k вниз — вероятен более глубокий откат.`,
      },
    ],
  },
  {
    id: 2,
    title: 'Альткоины',
    messages: [
      {
        role: 'user',
        content: 'Какие альткоины стоит смотреть в этом цикле?',
      },
      {
        role: 'assistant',
        content: `# Топ альткоинов для этого цикла

## 1. Solana (SOL) 🔥
**Текущая цена:** $98.50
**Потенциал:** $150-200

**Почему интересно:**
• Быстрая сеть (400ms блоки, 65k TPS)
• Рост DeFi экосистемы (+45% TVL за месяц)
• Сильная команда и инвесторы

**Риски:**
• История даунтаймов сети
• Высокая конкуренция (ETH L2, новые L1)

---

## 2. Avalanche (AVAX) ❄️
**Текущая цена:** $36.80
**Потенциал:** $50-70

**Почему интересно:**
• Subnet архитектура (кастомные блокчейны)
• Партнерства с традфи (Citi, JP Morgan тесты)
• Быстрый финалити (< 2 сек)

**Риски:**
• Централизация валидаторов
• Зависимость от хайпа вокруг subnets

---

## ⚠️ Правило управления рисками
Даже если проект выглядит сильно — **не вливай всё в один альт**. Диверсификация: 40% BTC/ETH, 60% альты (по 15-20% в каждый).`,
      },
    ],
  },
  {
    id: 3,
    title: 'Fear & Greed',
    messages: [
      {
        role: 'user',
        content: 'Что сейчас с Fear & Greed индексом?',
      },
      {
        role: 'assistant',
        content: `# Fear & Greed Index — Анализ

**Текущий индекс:** 28/100 — **Fear (Страх)** 😨

## Что это значит?
Индекс показывает **страх** на рынке. Инвесторы осторожничают, боятся дальнейшего падения и не спешат покупать.

## Исторический контекст
| Период | Индекс | Результат |
|--------|--------|-----------|
| Март 2020 | 10 (Extreme Fear) | BTC вырос +300% за год |
| Ноябрь 2021 | 84 (Extreme Greed) | Начало коррекции -50% |
| Июнь 2022 | 8 (Extreme Fear) | Дно рынка, рост +120% |
| **Сейчас** | **28 (Fear)** | **Хорошее время для покупок?** |

## Contrarian стратегия
> "Покупай, когда все боятся. Продавай, когда все жадничают."

**Что делать при Fear?**
✅ DCA (Dollar Cost Averaging) в качественные активы
✅ Набирать позиции постепенно
✅ Держать кэш для возможных просадок

Страх — это не плохо. Это **возможность** для тех, кто думает головой, а не эмоциями.`,
      },
    ],
  },
];

// Compact examples for hero - EN
const CHAT_EXAMPLES_EN: ChatExample[] = [
  {
    id: 1,
    title: 'BTC Technical Analysis',
    messages: [
      {
        role: 'user',
        content: 'Give me a full technical analysis of BTC right now',
      },
      {
        role: 'assistant',
        content: `# Bitcoin Technical Analysis

**Current price:** $43,250
**24h change:** +3.2% 📈

## Technical Indicators
\`\`\`
RSI (14):        62 → Neutral-Bullish
MACD:           Bullish crossover ✅
MA(50):         $41,800 → Support
MA(200):        $38,500 → Long-term trend
Volume:         Above average (+18%)
\`\`\`

## Key Levels
**Resistance:**
• $44,500 - strong level
• $46,000 - psychological barrier
• $48,000 - local high

**Support:**
• $42,000 - short-term
• $40,500 - important zone
• $38,000 - critical support

## Conclusion
BTC shows **bullish structure** on 4H timeframe. Breaking $44,500 could lead to $46-48k. If price retraces to $42k — this could be a good entry point.

⚠️ **Risks:** If we break below $40k — a deeper correction is likely.`,
      },
    ],
  },
  {
    id: 2,
    title: 'Altcoins',
    messages: [
      {
        role: 'user',
        content: 'Which altcoins should I watch this cycle?',
      },
      {
        role: 'assistant',
        content: `# Top Altcoins for This Cycle

## 1. Solana (SOL) 🔥
**Current price:** $98.50
**Potential:** $150-200

**Why interesting:**
• Fast network (400ms blocks, 65k TPS)
• Growing DeFi ecosystem (+45% TVL in a month)
• Strong team and investors

**Risks:**
• History of network downtimes
• High competition (ETH L2, new L1s)

---

## 2. Avalanche (AVAX) ❄️
**Current price:** $36.80
**Potential:** $50-70

**Why interesting:**
• Subnet architecture (custom blockchains)
• TradFi partnerships (Citi, JP Morgan tests)
• Fast finality (< 2 sec)

**Risks:**
• Validator centralization
• Dependence on subnet hype

---

## ⚠️ Risk Management Rule
Even if a project looks strong — **don't put everything in one alt**. Diversification: 40% BTC/ETH, 60% alts (15-20% each).`,
      },
    ],
  },
  {
    id: 3,
    title: 'Fear & Greed',
    messages: [
      {
        role: 'user',
        content: 'What about the Fear & Greed index now?',
      },
      {
        role: 'assistant',
        content: `# Fear & Greed Index — Analysis

**Current index:** 28/100 — **Fear** 😨

## What does this mean?
The index shows **fear** in the market. Investors are cautious, afraid of further decline and not rushing to buy.

## Historical Context
| Period | Index | Result |
|--------|-------|--------|
| March 2020 | 10 (Extreme Fear) | BTC +300% in a year |
| November 2021 | 84 (Extreme Greed) | Correction start -50% |
| June 2022 | 8 (Extreme Fear) | Market bottom, +120% growth |
| **Now** | **28 (Fear)** | **Good time to buy?** |

## Contrarian Strategy
> "Buy when everyone is afraid. Sell when everyone is greedy."

**What to do during Fear?**
✅ DCA (Dollar Cost Averaging) into quality assets
✅ Accumulate positions gradually
✅ Keep cash for possible dips

Fear is not bad. It's an **opportunity** for those who think with their head, not emotions.`,
      },
    ],
  },
];

export default function LiveChatExamplesCompact() {
  const locale = useCurrentLocale();
  const [currentExample, setCurrentExample] = useState(0);
  const [direction, setDirection] = useState(0);

  // Select examples based on locale
  const CHAT_EXAMPLES = locale === 'ru' ? CHAT_EXAMPLES_RU : CHAT_EXAMPLES_EN;

  const slideVariants = {
    enter: (direction: number) => ({
      x: direction > 0 ? 300 : -300,
      opacity: 0,
    }),
    center: {
      zIndex: 1,
      x: 0,
      opacity: 1,
    },
    exit: (direction: number) => ({
      zIndex: 0,
      x: direction < 0 ? 300 : -300,
      opacity: 0,
    }),
  };

  const swipeConfidenceThreshold = 10000;
  const swipePower = (offset: number, velocity: number) => {
    return Math.abs(offset) * velocity;
  };

  const paginate = (newDirection: number) => {
    setDirection(newDirection);
    setCurrentExample((prev) => {
      let next = prev + newDirection;
      if (next < 0) next = CHAT_EXAMPLES.length - 1;
      if (next >= CHAT_EXAMPLES.length) next = 0;
      return next;
    });
  };

  const example = CHAT_EXAMPLES[currentExample];

  return (
    <div className="w-full max-w-sm">
      {/* Carousel Container */}
      <div className="relative h-[480px]">
        <AnimatePresence initial={false} custom={direction}>
          <motion.div
            key={example.id}
            custom={direction}
            variants={slideVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{
              x: { type: 'spring', stiffness: 300, damping: 30 },
              opacity: { duration: 0.2 },
            }}
            drag="x"
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={1}
            onDragEnd={(_e, { offset, velocity }) => {
              const swipe = swipePower(offset.x, velocity.x);
              if (swipe < -swipeConfidenceThreshold) {
                paginate(1);
              } else if (swipe > swipeConfidenceThreshold) {
                paginate(-1);
              }
            }}
            className="absolute inset-0 cursor-grab active:cursor-grabbing"
          >
            {/* Phone Mock */}
            <div className="glass-panel p-6 rounded-3xl shadow-2xl w-full h-full flex flex-col">
              {/* Chat Header */}
              <div className="flex items-center gap-3 border-b border-white/10 pb-4 mb-4">
                <div className="w-10 h-10 rounded-xl overflow-hidden bg-black flex-shrink-0">
                  <Image
                    src="/syntra/aiminiature.png"
                    width={40}
                    height={40}
                    alt="Syntra AI"
                    className="object-cover"
                  />
                </div>
                <div>
                  <div className="text-sm font-semibold">Syntra AI</div>
                  <div className="text-xs text-white/40">
                    {locale === 'ru' ? 'бот · онлайн' : 'bot · online'}
                  </div>
                </div>
              </div>

              {/* Chat Messages - scrollable */}
              <div className="flex-1 overflow-y-auto pr-1 chat-scrollbar">
                <div className="chat space-y-3">
                  {example.messages.map((message, idx) => (
                    <div
                      key={idx}
                      className={`flex gap-2.5 ${
                        message.role === 'user' ? 'justify-end' : 'justify-start'
                      }`}
                    >
                      {/* AI Avatar */}
                      {message.role === 'assistant' && (
                        <div className="w-7 h-7 rounded-full bg-black overflow-hidden flex-shrink-0 self-start">
                          <Image
                            src="/syntra/aiminiature.png"
                            width={28}
                            height={28}
                            alt="AI"
                            className="object-cover"
                          />
                        </div>
                      )}

                      {/* Message Bubble */}
                      <div
                        className={`${
                          message.role === 'user'
                            ? 'bg-blue-600 text-white rounded-2xl px-4 py-2.5 max-w-[75%]'
                            : 'bg-white/5 border border-white/10 rounded-2xl px-4 py-2.5 max-w-[85%]'
                        }`}
                      >
                        {message.role === 'user' ? (
                          <p className="text-sm">{message.content}</p>
                        ) : (
                          <div className="prose prose-invert prose-sm max-w-none text-xs">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                code(props: any) {
                                  const { node, inline, className, children, ...rest } = props;
                                  const match = /language-(\w+)/.exec(className || '');
                                  return !inline && match ? (
                                    <SyntaxHighlighter
                                      style={oneDark}
                                      language={match[1]}
                                      PreTag="div"
                                      className="rounded-lg !mt-1 !mb-1"
                                      customStyle={{
                                        padding: '0.5rem',
                                        borderRadius: '0.5rem',
                                        fontSize: '10px',
                                      }}
                                      {...rest}
                                    >
                                      {String(children).replace(/\n$/, '')}
                                    </SyntaxHighlighter>
                                  ) : (
                                    <code
                                      className="bg-gray-700/50 px-1 py-0.5 rounded text-blue-300"
                                      style={{ fontSize: '10px' }}
                                      {...rest}
                                    >
                                      {children}
                                    </code>
                                  );
                                },
                                p: ({ children }) => (
                                  <p className="mb-2 last:mb-0 leading-relaxed text-gray-100">
                                    {children}
                                  </p>
                                ),
                                ul: ({ children }) => (
                                  <ul className="list-disc list-inside mb-2 space-y-1">
                                    {children}
                                  </ul>
                                ),
                                li: ({ children }) => <li className="text-gray-200">{children}</li>,
                                strong: ({ children }) => (
                                  <strong className="font-bold text-white">{children}</strong>
                                ),
                                h1: ({ children }) => (
                                  <h1 className="text-sm font-bold mb-2 text-white">{children}</h1>
                                ),
                                h2: ({ children }) => (
                                  <h2 className="text-xs font-bold mb-1.5 text-white">
                                    {children}
                                  </h2>
                                ),
                                h3: ({ children }) => (
                                  <h3 className="text-xs font-semibold mb-1 text-white">
                                    {children}
                                  </h3>
                                ),
                                table: ({ children }) => (
                                  <div className="overflow-x-auto my-2">
                                    <table className="min-w-full divide-y divide-gray-700">
                                      {children}
                                    </table>
                                  </div>
                                ),
                                th: ({ children }) => (
                                  <th className="px-2 py-1 text-left text-[10px] font-semibold text-gray-300 bg-gray-800/50">
                                    {children}
                                  </th>
                                ),
                                td: ({ children }) => (
                                  <td className="px-2 py-1 text-[10px] text-gray-400 border-t border-gray-700/50">
                                    {children}
                                  </td>
                                ),
                                blockquote: ({ children }) => (
                                  <blockquote className="border-l-2 border-blue-500 pl-2 italic text-gray-300 my-2">
                                    {children}
                                  </blockquote>
                                ),
                              }}
                            >
                              {message.content}
                            </ReactMarkdown>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </AnimatePresence>

        {/* Navigation Arrows - Compact */}
        <button
          onClick={() => paginate(-1)}
          className="absolute left-2 top-1/2 -translate-y-1/2 z-10 w-8 h-8 rounded-full bg-black/40 backdrop-blur-xl border border-white/20 flex items-center justify-center hover:bg-black/60 transition-all"
          aria-label="Previous"
        >
          <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <button
          onClick={() => paginate(1)}
          className="absolute right-2 top-1/2 -translate-y-1/2 z-10 w-8 h-8 rounded-full bg-black/40 backdrop-blur-xl border border-white/20 flex items-center justify-center hover:bg-black/60 transition-all"
          aria-label="Next"
        >
          <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* Dots Indicator */}
      <div className="flex justify-center gap-2 mt-4">
        {CHAT_EXAMPLES.map((_, idx) => (
          <button
            key={idx}
            onClick={() => {
              setDirection(idx > currentExample ? 1 : -1);
              setCurrentExample(idx);
            }}
            className={`h-1.5 rounded-full transition-all ${
              idx === currentExample
                ? 'bg-blue-500 w-6'
                : 'bg-white/20 hover:bg-white/40 w-1.5'
            }`}
            aria-label={`Example ${idx + 1}`}
          />
        ))}
      </div>

      <style jsx>{`
        .chat-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .chat-scrollbar::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.03);
          border-radius: 10px;
        }
        .chat-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(59, 130, 246, 0.4);
          border-radius: 10px;
        }
        .chat-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(59, 130, 246, 0.6);
        }
      `}</style>
    </div>
  );
}
