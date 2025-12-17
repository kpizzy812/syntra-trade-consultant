/**
 * Live Chat Examples Component
 * Реальные примеры чата с AI на основе реальной верстки
 * Свайп-карусель для переключения между примерами
 */

'use client';

import { useState } from 'react';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface ChatExample {
  id: number;
  title: string;
  description: string;
  messages: {
    role: 'user' | 'assistant';
    content: string;
  }[];
}

// Реальные примеры запросов к AI
const CHAT_EXAMPLES: ChatExample[] = [
  {
    id: 1,
    title: 'Технический анализ BTC',
    description: 'Глубокий анализ Bitcoin с индикаторами и уровнями',
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
    title: 'Анализ альткоинов',
    description: 'Разбор перспективных альткоинов с рисками',
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

## 3. Polygon (MATIC) 🔷
**Текущая цена:** $0.88
**Потенциал:** $1.50-2.00

**Почему интересно:**
• Масштабирование Ethereum (#1 по adoption)
• Интеграции с Disney, Starbucks, Reddit
• zkEVM технология

**Риски:**
• Сильная конкуренция среди L2
• Переход на новую токеномику (POL)

---

## ⚠️ Правило управления рисками
Даже если проект выглядит сильно — **не вливай всё в один альт**. Диверсификация: 40% BTC/ETH, 60% альты (по 15-20% в каждый).

Не забывай про стоп-лоссы и фиксацию прибыли по пути вверх.`,
      },
    ],
  },
  {
    id: 3,
    title: 'Fear & Greed Index',
    description: 'Анализ настроений рынка и стратегия действий',
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

**Чего НЕ делать:**
❌ Паниковать и продавать в минус
❌ Входить all-in одной суммой
❌ Игнорировать риски и менеджмент капитала

## Сигналы разворота
Следи за:
• Пробой важных уровней сопротивления
• Рост объемов торговли
• Позитивные новости (ETF, регуляция, adoptions)

Страх — это не плохо. Это **возможность** для тех, кто думает головой, а не эмоциями.`,
      },
    ],
  },
  {
    id: 4,
    title: 'Управление рисками',
    description: 'Как правильно управлять капиталом в крипте',
    messages: [
      {
        role: 'user',
        content: 'Как правильно управлять рисками при трейдинге?',
      },
      {
        role: 'assistant',
        content: `# Risk Management — Библия трейдера

## 1. Правило 2% 📊
**Никогда не рискуй больше 2% капитала в одной сделке.**

Пример:
\`\`\`
Депозит:     $10,000
Риск 2%:     $200
Стоп-лосс:   5% от цены входа

Размер позиции = $200 / 0.05 = $4,000
\`\`\`

Даже если будет 10 убыточных сделок подряд — ты потеряешь только 20% депозита, а не всё.

---

## 2. Risk/Reward минимум 1:2 📈
**Потенциальная прибыль должна быть минимум вдвое больше риска.**

Пример:
• Вход: $100
• Стоп-лосс: $95 (риск $5)
• Take-profit: $110 (профит $10)
• **R:R = 1:2 ✅**

Если ты будешь прав даже в 40% случаев — ты в плюсе.

---

## 3. Диверсификация 🎯
**Не держи всё в одной корзине.**

Оптимальный портфель:
\`\`\`
BTC:          30-40%  → Надежность
ETH:          20-30%  → Экосистема
Top 10 Alts:  20-30%  → Рост
Новые проекты: 10%    → Риск/высокий профит
Stablecoins:  10-20%  → Ликвидность
\`\`\`

---

## 4. Эмоции под контролем 🧠
Самый большой враг трейдера — **его собственная психология**.

**Типичные ошибки:**
❌ FOMO (боязнь упустить) → Вход на хаях
❌ Panic Selling → Продажа на дне
❌ Revenge Trading → Попытка отыграться после убытка
❌ Over-leveraging → Чрезмерное плечо

**Решение:**
✅ Торговый план (и следование ему!)
✅ Торговый журнал (записывай сделки)
✅ Перерывы (если эмоции зашкаливают)

---

## 5. Стоп-лоссы — ОБЯЗАТЕЛЬНЫ ⛔
**Всегда ставь стоп-лосс ДО входа в позицию.**

Рынок может сделать всё что угодно. Стоп-лосс — твоя страховка от катастрофы.

---

## Итог
Risk management это не "про трусость". Это про **выживание и долгосрочную прибыль**.

Лучше заработать 50% за год со стабильной стратегией, чем потерять 80% капитала на одной "гениальной" сделке.`,
      },
    ],
  },
  {
    id: 5,
    title: 'Рыночные циклы',
    description: 'Понимание циклов крипторынка и когда покупать',
    messages: [
      {
        role: 'user',
        content: 'Объясни как работают циклы в крипте и где мы сейчас?',
      },
      {
        role: 'assistant',
        content: `# Крипто-циклы — Понимание рынка

## 4 фазы рыночного цикла

### 1. Аккумуляция (Дно) 📉💰
**Признаки:**
• Цены на минимумах
• Все говорят "крипта умерла"
• Fear & Greed: Extreme Fear (0-20)
• Низкие объемы торговли
• Смарт-мани набирает позиции

**Что делать:** 🟢 **ПОКУПАТЬ** (DCA, держать долгосрочно)

---

### 2. Бычий рынок (Рост) 📈🚀
**Признаки:**
• Устойчивый рост цен
• Пробой важных сопротивлений
• Объемы торговли растут
• Позитивные новости в СМИ
• Альткоины начинают "взлетать"

**Что делать:** 🟡 **ДЕРЖАТЬ** (можно добирать на откатах)

---

### 3. Распределение (Вершина) 📈💸
**Признаки:**
• "Все" зарабатывают в крипте
• Таксисты дают советы по альткоинам
• Fear & Greed: Extreme Greed (80-100)
• Взрывной рост мем-коинов
• Твои родители спрашивают про крипту 😅

**Что делать:** 🔴 **ФИКСИРОВАТЬ ПРИБЫЛЬ** (продавать частями)

---

### 4. Медвежий рынок (Падение) 📉😱
**Признаки:**
• Резкое падение цен (-50-80%)
• Массовая паника и капитуляция
• Проекты закрываются
• СМИ: "Крипта это пирамида"
• Все забывают про крипту

**Что делать:** 🟠 **ЖДАТЬ** (держать кэш, готовиться к фазе 1)

---

## Где мы сейчас? 🤔

**Моя оценка:** Между фазой 1 и 2 (Конец аккумуляции / Начало роста)

**Почему:**
✅ BTC восстановился после медвежки 2022
✅ Institutional adoption растет (ETF на подходе)
✅ Fear & Greed на уровне 28-40 (умеренный страх)
✅ Альткоины еще не в полном памп-режиме

**Что это значит:**
Это **хорошее время для постепенного набора позиций**. Не all-in, но и не сидеть полностью в кэше.

---

## Исторические циклы Bitcoin

| Цикл | Дно | Вершина | Рост | Падение |
|------|-----|---------|------|---------|
| 2015-2017 | $200 | $20,000 | +9,900% | -83% |
| 2018-2021 | $3,200 | $69,000 | +2,056% | -77% |
| 2022-202? | $15,500 | **???** | **???** | **???** |

**Закономерность:**
Каждый цикл → пик ниже предыдущего в % росте, но **абсолютные цифры растут**.

---

## Главное правило циклов
> "Быки зарабатывают. Медведи зарабатывают. Свиньи идут на бойню."

Не будь свиньёй. Фиксируй прибыль по пути вверх. Не жди "луны" когда уже +500%.`,
      },
    ],
  },
];

export default function LiveChatExamples() {
  const [currentExample, setCurrentExample] = useState(0);
  const [direction, setDirection] = useState(0);

  // Debug: проверяем что компонент рендерится
  console.log('🎯 LiveChatExamples rendered, current example:', currentExample);

  const slideVariants = {
    enter: (direction: number) => ({
      x: direction > 0 ? 1000 : -1000,
      opacity: 0,
    }),
    center: {
      zIndex: 1,
      x: 0,
      opacity: 1,
    },
    exit: (direction: number) => ({
      zIndex: 0,
      x: direction < 0 ? 1000 : -1000,
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
    <div className="relative">
      {/* Title & Description */}
      <div className="text-center mb-6">
        <motion.h2
          className="text-2xl md:text-3xl font-semibold mb-2"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          Посмотри как работает AI
        </motion.h2>
        <motion.p
          className="text-sm text-white/70 max-w-2xl mx-auto"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
        >
          Реальные примеры из чата. Свайпай или кликай по стрелкам.
        </motion.p>
      </div>

      {/* Carousel Container - Phone Mock Style */}
      <div className="relative flex justify-center">
        <div className="relative w-full max-w-md">
          {/* Example Title */}
          <div className="text-center mb-3">
            <AnimatePresence mode="wait">
              <motion.h3
                key={example.id}
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 5 }}
                transition={{ duration: 0.2 }}
                className="text-base font-semibold text-white/90"
              >
                {example.title}
              </motion.h3>
            </AnimatePresence>
          </div>

          {/* Phone Mock Container */}
          <div className="relative h-[550px] md:h-[600px]">
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
                {/* Phone Mock - как в hero */}
                <div className="glass-panel p-4 rounded-3xl shadow-2xl w-full h-full flex flex-col">
                  {/* Chat Header */}
                  <div className="flex items-center gap-3 border-b border-white/10 pb-3 mb-3">
                    <div className="w-9 h-9 rounded-xl overflow-hidden bg-black flex-shrink-0">
                      <Image
                        src="/syntra/aiminiature.png"
                        width={36}
                        height={36}
                        alt="Syntra AI"
                        className="object-cover"
                      />
                    </div>
                    <div>
                      <div className="text-sm font-semibold">Syntra AI</div>
                      <div className="text-xs text-white/40">бот · онлайн</div>
                    </div>
                  </div>

                  {/* Chat Messages - scrollable */}
                  <div className="flex-1 overflow-y-auto pr-1 chat-scrollbar">
                    <div className="chat space-y-2.5">
                      {example.messages.map((message, idx) => (
                        <div
                          key={idx}
                          className={`flex gap-2 ${
                            message.role === 'user' ? 'justify-end' : 'justify-start'
                          }`}
                        >
                          {/* AI Avatar */}
                          {message.role === 'assistant' && (
                            <div className="w-6 h-6 rounded-full bg-black overflow-hidden flex-shrink-0 self-start">
                              <Image
                                src="/syntra/aiminiature.png"
                                width={24}
                                height={24}
                                alt="AI"
                                className="object-cover"
                              />
                            </div>
                          )}

                          {/* Message Bubble */}
                          <div
                            className={`${
                              message.role === 'user'
                                ? 'msg user max-w-[80%]'
                                : 'msg bot max-w-[85%]'
                            }`}
                          >
                            {message.role === 'user' ? (
                              <p className="text-[11px] leading-relaxed">{message.content}</p>
                            ) : (
                              <div className="prose prose-invert prose-sm max-w-none text-[11px]">
                                <ReactMarkdown
                                  remarkPlugins={[remarkGfm]}
                                  components={{
                                    code(props: any) {
                                      const { node, inline, className, children, ...rest } =
                                        props;
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
                                      <p className="mb-1.5 last:mb-0 leading-relaxed">
                                        {children}
                                      </p>
                                    ),
                                    ul: ({ children }) => (
                                      <ul className="list-disc list-inside mb-1.5 space-y-0.5">
                                        {children}
                                      </ul>
                                    ),
                                    ol: ({ children }) => (
                                      <ol className="list-decimal list-inside mb-1.5 space-y-0.5">
                                        {children}
                                      </ol>
                                    ),
                                    li: ({ children }) => <li className="text-gray-200">{children}</li>,
                                    strong: ({ children }) => (
                                      <strong className="font-bold text-white">{children}</strong>
                                    ),
                                    h1: ({ children }) => (
                                      <h1 className="text-sm font-bold mb-1.5 text-white">{children}</h1>
                                    ),
                                    h2: ({ children }) => (
                                      <h2 className="text-xs font-bold mb-1 text-white">{children}</h2>
                                    ),
                                    h3: ({ children }) => (
                                      <h3 className="text-xs font-semibold mb-1 text-white">{children}</h3>
                                    ),
                                    table: ({ children }) => (
                                      <div className="overflow-x-auto my-1.5">
                                        <table className="min-w-full divide-y divide-gray-700">
                                          {children}
                                        </table>
                                      </div>
                                    ),
                                    th: ({ children }) => (
                                      <th className="px-1.5 py-0.5 text-left text-[10px] font-semibold text-gray-300 bg-gray-800/50">
                                        {children}
                                      </th>
                                    ),
                                    td: ({ children }) => (
                                      <td className="px-1.5 py-0.5 text-[10px] text-gray-400 border-t border-gray-700/50">
                                        {children}
                                      </td>
                                    ),
                                    blockquote: ({ children }) => (
                                      <blockquote className="border-l-2 border-blue-500 pl-2 italic text-gray-300 my-1.5">
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
        </div>
      </div>

      {/* CTA */}
      <div className="text-center mt-6">
        <p className="text-xs text-white/50 mb-3">
          Попробуй сам — открой бота и задай вопрос
        </p>
        <a
          href="https://t.me/SyntraAI_bot"
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-primary"
        >
          Открыть @SyntraAI_bot
        </a>
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
