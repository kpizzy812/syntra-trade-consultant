# 🚀 Syntra Mini App - Полный План Разработки

> **Дата создания**: 2025-01-18
> **Статус**: В разработке
> **Приоритет**: Chat-first дизайн уровня Apple/OpenAI/Anthropic

---

## 📋 Содержание

1. [Архитектура приложения](#архитектура-приложения)
2. [Система подписок и рефералов](#система-подписок-и-рефералов)
3. [Структура TabBar](#структура-tabbar)
4. [Детальное описание страниц](#детальное-описание-страниц)
5. [Backend API](#backend-api)
6. [План реализации](#план-реализации)
7. [Прогресс-трекер](#прогресс-трекер)

---

## 🎯 Архитектура приложения

### Главная фишка: **CHAT**
Mini App - это **визуальный интерфейс** для существующего AI-бота с фокусом на:
- 💬 Вылизанный чат (как Claude.ai, ChatGPT, Anthropic)
- 📊 Визуальная аналитика (графики, индикаторы)
- 💎 Управление подпиской
- 👥 Реферальная система
- ⭐ Watchlist избранных монет

### Отличие от бота:
| **Telegram Bot** | **Mini App** |
|---|---|
| Текстовый интерфейс | Визуальный UI |
| Команды (/price, /analyze) | Интерактивные карточки |
| Vision анализ (фото графиков) | Живые графики |
| Базовое форматирование | Markdown, code highlighting |
| Уведомления | Real-time обновления |

---

## 🔐 Система подписок и рефералов

### Subscription Tiers (из БД)

```typescript
enum SubscriptionTier {
  FREE = "free",     // 5 requests/day
  BASIC = "basic",   // 20 requests/day
  PREMIUM = "premium", // 100 requests/day
  VIP = "vip"       // Unlimited
}
```

#### Pricing (Telegram Stars):
| Tier | 1 месяц | 3 месяца (-15%) | 12 месяцев (-25%) |
|------|---------|-----------------|-------------------|
| **BASIC** | $4.99 (384⭐) | $12.72 (978⭐) | $44.91 (3453⭐) |
| **PREMIUM** | $24.99 (1923⭐) | $63.72 (4899⭐) | $224.91 (17298⭐) |
| **VIP** | $49.99 (3845⭐) | $127.47 (9802⭐) | $449.91 (34597⭐) |

### Payment Providers

```typescript
enum PaymentProvider {
  TELEGRAM_STARS = "telegram_stars",  // ✅ Реализовано
  TON_CONNECT = "ton_connect",        // 🔜 Будущее
  CRYPTO_BOT = "crypto_bot"           // 🔜 Опционально
}
```

### Referral System

#### Tier Levels:
| Tier | Referrals | Monthly Bonus | Discount | Revenue Share |
|------|-----------|---------------|----------|---------------|
| 🥉 **Bronze** | 0-4 | 0 | 0% | 0% |
| 🥈 **Silver** | 5-14 | +5 requests | 5% | 5% |
| 🥇 **Gold** | 15-49 | +15 requests | 10% | 10% |
| 💎 **Platinum** | 50+ | +30 requests | 15% | 15% |

#### Revenue Share:
- Platinum tier получает 15% от покупок рефералов
- Баланс в USD
- Минимальный вывод: $10
- Комиссия вывода: 5%
- Можно тратить на подписку (+20% bonus discount)

---

## 📱 Структура TabBar

```
┌────────┬────────┬──────────┬──────────┬─────────┐
│  Home  │  Chat  │Analytics │ Referral │ Profile │
└────────┴────────┴──────────┴──────────┴─────────┘
```

### Приоритеты:
1. **Chat** - главная фишка (50% времени разработки)
2. **Profile** - подписка + settings (20%)
3. **Home** - dashboard (15%)
4. **Referral** - реферальная система (10%)
5. **Analytics** - визуализация данных (5%)

---

## 🏠 1. Home - Market Dashboard

### Секции:

#### A) Fear & Greed Index Card
```typescript
<FearGreedCard>
  <CircularGauge value={25} />
  <Label>😱 Extreme Fear</Label>
  <Description>Good time to buy?</Description>
</FearGreedCard>
```

#### B) Watchlist
```typescript
<WatchlistSection>
  <Header>
    ⭐ Your Watchlist (3)
    <AddButton />
  </Header>

  <CoinList>
    <CoinCard symbol="BTC" price="$45,230" change="+2.4%" />
    <CoinCard symbol="ETH" price="$2,890" change="+1.8%" />
    <CoinCard symbol="SOL" price="$108.50" change="-0.5%" />
  </CoinList>
</WatchlistSection>
```

#### C) Top Movers (24h)
```typescript
<TopMoversSection>
  <Column>
    <Header>🔥 Gainers</Header>
    <MoverCard symbol="XRP" change="+12.5%" />
    <MoverCard symbol="ADA" change="+8.3%" />
  </Column>

  <Column>
    <Header>📉 Losers</Header>
    <MoverCard symbol="DOGE" change="-8.2%" />
    <MoverCard symbol="SHIB" change="-6.1%" />
  </Column>
</TopMoversSection>
```

#### D) Quick Actions
```typescript
<QuickActions>
  <ActionButton onClick={navigateToChat}>
    💬 Ask AI about market
  </ActionButton>
  <ActionButton onClick={navigateToAnalytics}>
    📊 View full analytics
  </ActionButton>
</QuickActions>
```

### API Endpoints:
- `GET /api/market/fear-greed` - Fear & Greed Index
- `GET /api/user/watchlist` - User's watchlist
- `POST /api/user/watchlist` - Add to watchlist
- `DELETE /api/user/watchlist/:symbol` - Remove from watchlist
- `GET /api/market/movers` - Top gainers/losers

---

## 💬 2. Chat - ГЛАВНАЯ ФИШКА

### Дизайн-требования (Apple/OpenAI уровень):

#### A) Message Rendering
```typescript
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  tokens_used?: number;
  model?: string;
}
```

**Компоненты:**
- `<UserMessage>` - справа, синий градиент
- `<AssistantMessage>` - слева, glassmorphism card
- `<TypingIndicator>` - три точки анимированные
- `<MessageActions>` - copy, regenerate

#### B) Markdown Support
```typescript
// Libraries:
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
```

**Поддержка:**
- ✅ Bold, italic, strikethrough
- ✅ Headers (h1-h6)
- ✅ Lists (ordered, unordered)
- ✅ Code blocks с syntax highlighting
- ✅ Inline code
- ✅ Blockquotes
- ✅ Tables

#### C) Streaming Implementation
```typescript
const streamChatResponse = async (message: string) => {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `tma ${initDataRaw}`,
    },
    body: JSON.stringify({ message }),
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  let assistantMessage = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    assistantMessage += chunk;

    // Update UI in real-time
    setMessages(prev => updateLastMessage(prev, assistantMessage));
  }
};
```

#### D) Chat Features
```typescript
// 1. Suggested Prompts
const suggestedPrompts = [
  "Analyze BTC right now",
  "What's the market sentiment?",
  "Show me top altcoins",
  "Fear & Greed analysis",
];

// 2. Message Actions
<MessageActions>
  <CopyButton onClick={() => copyToClipboard(content)} />
  <RegenerateButton onClick={() => regenerateResponse()} />
</MessageActions>

// 3. Context Display
<ContextIndicator>
  History: Last 5 messages
</ContextIndicator>

// 4. Token/Cost Display (для админов)
<MessageMeta>
  {tokens_used} tokens • {model} • $0.0023
</MessageMeta>
```

#### E) Chat History Sync
```typescript
// История синхронизируется с ботом через БД (ChatHistory)
// При загрузке Mini App:
const loadChatHistory = async () => {
  const history = await fetch('/api/chat/history?limit=50');
  setMessages(history.data);
};

// При отправке сообщения:
// 1. Сохраняется в ChatHistory (БД)
// 2. Доступно и в боте, и в Mini App
```

### API Endpoints:
- `POST /api/chat/stream` - Streaming chat (SSE или WebSocket)
- `GET /api/chat/history` - Получить историю (limit, offset)
- `POST /api/chat/regenerate` - Регенерировать последний ответ
- `DELETE /api/chat/history` - Очистить историю

---

## 📊 3. Analytics

### Structure:

#### A) Symbol Selector
```typescript
<AnalyticsPage>
  <SymbolSearch placeholder="Search BTC, ETH, SOL..." />

  <PopularCoins>
    <CoinChip symbol="BTC" active={selected === 'BTC'} />
    <CoinChip symbol="ETH" />
    <CoinChip symbol="SOL" />
    <CoinChip symbol="BNB" />
  </PopularCoins>

  <WatchlistSection>
    <Header>⭐ Your Watchlist</Header>
    <WatchlistCoins />
  </WatchlistSection>
</AnalyticsPage>
```

#### B) Analytics Display (Tabs)
```typescript
<AnalyticsTabs>
  <Tab name="Overview">
    <PriceCard price={45230} change24h={2.4} />
    <MiniChart data={chartData} />
    <QuickStats volume={28.5B} mcap={890B} rank={1} />
  </Tab>

  <Tab name="Technicals">
    <RSIIndicator value={65.4} />
    <MACDChart macd={...} signal={...} histogram={...} />
    <BollingerBands upper={...} middle={...} lower={...} />
    <MovingAverages ma20={...} ma50={...} ma200={...} />
    <CandlestickPatterns patterns={['Doji', 'Hammer']} />
  </Tab>

  <Tab name="On-Chain">
    <ActiveAddresses value={...} trend="up" />
    <ExchangeFlows inflow={...} outflow={...} />
    <NetworkHealth metrics={...} />
  </Tab>

  <Tab name="Sentiment">
    <FundingRates rate={0.01} sentiment="bullish" />
    <NewsSentiment score={0.75} />
    <AISummary>Market is showing bullish signals...</AISummary>
  </Tab>
</AnalyticsTabs>
```

### API Endpoints:
- `GET /api/analytics/:symbol/overview` - Цена, chart, stats
- `GET /api/analytics/:symbol/technicals` - TA индикаторы
- `GET /api/analytics/:symbol/onchain` - On-chain метрики
- `GET /api/analytics/:symbol/sentiment` - Funding rates, news

---

## 👥 4. Referral

### Sections:

#### A) Referral Link
```typescript
<ReferralLinkCard>
  <Title>Your Referral Link</Title>
  <LinkDisplay>
    t.me/syntra_bot?start=ref_ABC123
  </LinkDisplay>
  <Actions>
    <CopyButton />
    <ShareButton /> {/* Telegram share */}
  </Actions>
</ReferralLinkCard>
```

#### B) Stats Card
```typescript
<ReferralStatsCard>
  <TierBadge tier="gold">🥇 Gold</TierBadge>

  <Stats>
    <Stat label="Total Referrals" value={23} />
    <Stat label="Active" value={18} />
    <Stat label="Premium Converted" value={5} />
  </Stats>

  <Rewards>
    <Reward>+15 monthly bonus requests</Reward>
    <Reward>10% discount on subscriptions</Reward>
    <Reward>10% revenue share</Reward>
  </Rewards>

  <ProgressBar>
    Next tier: Platinum (need 27 more active referrals)
  </ProgressBar>
</ReferralStatsCard>
```

#### C) Balance Card
```typescript
<BalanceCard>
  <CurrentBalance>$23.45</CurrentBalance>
  <BalanceDetails>
    <Detail label="Earned (total)" value="$45.20" />
    <Detail label="Withdrawn" value="$15.00" />
    <Detail label="Spent" value="$6.75" />
  </BalanceDetails>

  <RevenueShare30d>
    Last 30 days: $8.30
  </RevenueShare30d>

  <Actions>
    {balance >= 10 && <WithdrawButton />}
    {balance > 0 && <UseForSubscriptionButton />}
  </Actions>
</BalanceCard>
```

#### D) Leaderboard
```typescript
<LeaderboardCard>
  <Title>🏆 Top Referrers</Title>

  <LeaderList>
    <LeaderItem rank={1} medal="🥇">
      @username1 — 156 referrals 💎
    </LeaderItem>
    <LeaderItem rank={2} medal="🥈">
      @username2 — 89 referrals 🥇
    </LeaderItem>
    ...
  </LeaderList>

  {userRank > 10 && (
    <UserRank>
      ...
      #{userRank} You — {userReferrals} referrals
    </UserRank>
  )}
</LeaderboardCard>
```

#### E) Tier Info
```typescript
<TierInfoModal>
  <TierCard tier="bronze">
    🥉 Bronze (0-4 referrals)
    No bonuses yet
  </TierCard>

  <TierCard tier="silver">
    🥈 Silver (5-14 referrals)
    • +5 monthly requests
    • 5% discount
    • 5% revenue share
  </TierCard>

  <TierCard tier="gold">
    🥇 Gold (15-49 referrals)
    • +15 monthly requests
    • 10% discount
    • 10% revenue share
  </TierCard>

  <TierCard tier="platinum">
    💎 Platinum (50+ referrals)
    • +30 monthly requests
    • 15% discount
    • 15% revenue share
  </TierCard>
</TierInfoModal>
```

### API Endpoints:
- `GET /api/referral/stats` - Статистика рефералов
- `GET /api/referral/balance` - Баланс
- `GET /api/referral/leaderboard` - Leaderboard
- `POST /api/referral/withdraw` - Запрос на вывод

---

## 👤 5. Profile

### Sections:

#### A) User Card
```typescript
<UserProfileCard>
  <Avatar>{user.first_name[0]}</Avatar>

  <UserInfo>
    <Name>{user.first_name}</Name>
    <Username>@{user.username}</Username>
  </UserInfo>

  {user.subscription?.tier !== 'free' && (
    <PremiumBadge tier={user.subscription.tier}>
      ⭐ {tierName}
    </PremiumBadge>
  )}
</UserProfileCard>
```

#### B) Subscription Section
```typescript
<SubscriptionSection>
  {!isPremium ? (
    <UpgradeCard>
      <Title>💎 Upgrade to Premium</Title>

      <Benefits>
        ✅ Unlimited AI requests (or tier limit)
        ✅ Advanced analytics
        ✅ Priority support
        ✅ Early access to features
      </Benefits>

      <PricingPreview>
        From $4.99/month
      </PricingPreview>

      <UpgradeButton onClick={openPurchaseModal}>
        Upgrade Now
      </UpgradeButton>
    </UpgradeCard>
  ) : (
    <ActiveSubscriptionCard>
      <TierBadge>{tierName}</TierBadge>
      <ExpiresAt>Active until {expiresAt}</ExpiresAt>
      <DaysLeft>{daysLeft} days left</DaysLeft>
      <AutoRenew enabled={autoRenew} />

      <Actions>
        <ChangePlanButton />
        <CancelAutoRenewButton />
      </Actions>
    </ActiveSubscriptionCard>
  )}
</SubscriptionSection>
```

#### C) Purchase Modal (КЛЮЧЕВОЙ КОМПОНЕНТ)
```typescript
<PurchaseModal>
  {/* Step 1: Select Tier */}
  <TierSelection>
    <TierOption tier="basic">
      💼 BASIC
      20 requests/day
      From $4.99/mo
    </TierOption>

    <TierOption tier="premium" popular>
      💎 PREMIUM
      100 requests/day
      From $24.99/mo
    </TierOption>

    <TierOption tier="vip">
      👑 VIP
      Unlimited
      From $49.99/mo
    </TierOption>
  </TierSelection>

  {/* Step 2: Select Duration */}
  <DurationSelection tier={selectedTier}>
    <DurationOption months={1}>
      1 month
      {price}⭐ ($4.99)
    </DurationOption>

    <DurationOption months={3} discount={15}>
      3 months
      {price}⭐ ($12.72)
      🎁 Save 15%
    </DurationOption>

    <DurationOption months={12} discount={25} recommended>
      1 year
      {price}⭐ ($44.91)
      🎁 Save 25%
    </DurationOption>
  </DurationSelection>

  {/* Step 3: Payment Method Selection */}
  <PaymentMethodSelection>
    <PaymentOption provider="telegram_stars" default>
      ⭐ Telegram Stars
      {starsAmount} Stars
    </PaymentOption>

    <PaymentOption provider="ton_connect" comingSoon>
      💎 TON Connect
      Pay with TON/USDT
      🔜 Coming Soon
    </PaymentOption>

    <PaymentOption provider="crypto_bot" comingSoon>
      🤖 CryptoBot
      Multiple cryptocurrencies
      🔜 Coming Soon
    </PaymentOption>

    {balance > 0 && (
      <PaymentOption provider="balance">
        💰 Use Balance
        Current: ${balance}
        +20% bonus discount
      </PaymentOption>
    )}
  </PaymentMethodSelection>

  {/* Step 4: Confirmation */}
  <PurchaseConfirmation>
    <Summary>
      <Item>Plan: {tierName}</Item>
      <Item>Duration: {duration}</Item>
      <Item>Payment: {provider}</Item>
      {discount > 0 && <Item>Discount: -{discount}%</Item>}
      {referralDiscount > 0 && <Item>Referral discount: -{referralDiscount}%</Item>}
      {useBalance && <Item>Balance discount: +20%</Item>}
    </Summary>

    <TotalPrice>
      Total: {finalAmount} {currency}
    </TotalPrice>

    <PurchaseButton onClick={handlePurchase}>
      {provider === 'telegram_stars' ? 'Pay with Stars' : 'Continue'}
    </PurchaseButton>
  </PurchaseConfirmation>
</PurchaseModal>
```

**Purchase Flow:**
```typescript
const handlePurchase = async () => {
  if (provider === 'telegram_stars') {
    // 1. Create invoice via backend
    const invoice = await createInvoice({
      tier, duration, provider: 'telegram_stars'
    });

    // 2. Show Telegram payment UI (automatic)
    // Telegram handles payment UI

    // 3. Listen for successful_payment event
    // Backend processes payment and activates subscription

  } else if (provider === 'ton_connect') {
    // TON Connect flow (future)
    connectTonWallet();

  } else if (provider === 'balance') {
    // Use balance
    const result = await purchaseWithBalance({ tier, duration });
    if (result.success) {
      showSuccess();
      refreshSubscription();
    }
  }
};
```

#### D) Usage Stats
```typescript
<UsageStatsCard>
  <Title>📊 This Month</Title>

  <Stat>
    <Label>AI Requests</Label>
    <Value>{used} / {limit}</Value>
    <ProgressBar progress={used / limit * 100} />
  </Stat>

  <Stat>
    <Label>Vision Analyses</Label>
    <Value>{visionUsed}</Value>
  </Stat>

  <Stat>
    <Label>Cost Saved</Label>
    <Value>${costSaved}</Value>
  </Stat>
</UsageStatsCard>
```

#### E) Settings
```typescript
<SettingsSection>
  <SettingItem>
    <Label>Language</Label>
    <Select value={language} onChange={changeLanguage}>
      <Option value="ru">🇷🇺 Русский</Option>
      <Option value="en">🇬🇧 English</Option>
    </Select>
  </SettingItem>

  <SettingItem>
    <Label>Notifications</Label>
    <Toggle enabled={notifications} />
  </SettingItem>

  <SettingItem>
    <Label>Theme</Label>
    <Value>Dark</Value>
  </SettingItem>

  <DangerZone>
    <ClearChatHistoryButton />
    <DeleteAccountButton />
  </DangerZone>
</SettingsSection>
```

#### F) Quick Links
```typescript
<QuickLinksSection>
  <LinkButton onClick={navigateToReferral}>
    👥 Invite Friends
    You have {referralCount} referrals
  </LinkButton>

  <LinkButton onClick={openSupport}>
    💬 Support
  </LinkButton>

  <LinkButton onClick={openDocs}>
    📖 Documentation
  </LinkButton>
</QuickLinksSection>
```

### API Endpoints:
- `GET /api/user/profile` - Профиль пользователя
- `GET /api/user/subscription` - Текущая подписка
- `POST /api/purchase/create-invoice` - Создать invoice
- `POST /api/purchase/with-balance` - Купить за balance
- `GET /api/user/usage-stats` - Статистика использования
- `PATCH /api/user/settings` - Обновить настройки

---

## 🔧 Backend API

### Authentication
```typescript
// Все запросы используют Telegram initData для авторизации
headers: {
  'Authorization': `tma ${initDataRaw}`
}

// Backend валидирует через:
// src/api/auth.py -> validate_telegram_init_data()
```

### Новые эндпоинты для Mini App:

#### Market API
```python
# src/api/market.py

@router.get("/market/fear-greed")
async def get_fear_greed_index():
    """Get current Fear & Greed Index"""
    pass

@router.get("/market/movers")
async def get_top_movers(limit: int = 10):
    """Get top gainers and losers (24h)"""
    pass
```

#### Watchlist API
```python
# src/api/watchlist.py

@router.get("/user/watchlist")
async def get_watchlist(user: User = Depends(get_current_user)):
    """Get user's watchlist"""
    pass

@router.post("/user/watchlist")
async def add_to_watchlist(symbol: str, user: User = Depends(get_current_user)):
    """Add coin to watchlist"""
    pass

@router.delete("/user/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str, user: User = Depends(get_current_user)):
    """Remove coin from watchlist"""
    pass
```

#### Chat API
```python
# src/api/chat.py

@router.post("/chat/stream")
async def stream_chat_response(
    message: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Stream AI chat response (SSE)"""
    pass

@router.get("/chat/history")
async def get_chat_history(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get chat history"""
    pass

@router.delete("/chat/history")
async def clear_chat_history(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Clear chat history"""
    pass
```

#### Analytics API
```python
# src/api/analytics.py

@router.get("/analytics/{symbol}/overview")
async def get_analytics_overview(symbol: str):
    """Get price, chart, basic stats"""
    pass

@router.get("/analytics/{symbol}/technicals")
async def get_technical_analysis(symbol: str):
    """Get TA indicators (RSI, MACD, BB, MA, etc.)"""
    pass

@router.get("/analytics/{symbol}/onchain")
async def get_onchain_metrics(symbol: str):
    """Get on-chain metrics (if supported)"""
    pass

@router.get("/analytics/{symbol}/sentiment")
async def get_sentiment_analysis(symbol: str):
    """Get funding rates, news sentiment"""
    pass
```

#### Purchase API
```python
# src/api/purchase.py

@router.post("/purchase/create-invoice")
async def create_purchase_invoice(
    tier: SubscriptionTier,
    duration_months: int,
    provider: PaymentProvider,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create subscription invoice"""
    pass

@router.post("/purchase/with-balance")
async def purchase_with_balance(
    tier: SubscriptionTier,
    duration_months: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Purchase subscription using referral balance"""
    pass
```

---

## 📝 План реализации

### Фаза 1: Frontend Foundation (Day 1-2)
- [x] ~~Структура уже создана~~ (из MINI_APP_DEVELOPMENT_PLAN)
- [ ] Переделать `frontend/app/page.tsx` (Home) под новый дизайн
- [ ] Создать UI компоненты:
  - [ ] `FearGreedCard.tsx`
  - [ ] `WatchlistSection.tsx`
  - [ ] `TopMoversSection.tsx`
  - [ ] `QuickActions.tsx`

### Фаза 2: Chat Implementation (Day 3-5) **ПРИОРИТЕТ #1**
- [ ] Создать `frontend/app/chat/page.tsx`
- [ ] Компоненты чата:
  - [ ] `ChatMessage.tsx` (user/assistant)
  - [ ] `MessageList.tsx` (с виртуализацией)
  - [ ] `ChatInput.tsx` (с suggested prompts)
  - [ ] `TypingIndicator.tsx`
  - [ ] `MessageActions.tsx` (copy, regenerate)
- [ ] Markdown рендеринг:
  - [ ] Установить `react-markdown`, `remark-gfm`
  - [ ] Установить `react-syntax-highlighter`
  - [ ] Кастомные компоненты для markdown
- [ ] Streaming:
  - [ ] Backend SSE endpoint `/api/chat/stream`
  - [ ] Frontend streaming client
  - [ ] Real-time UI updates
- [ ] История:
  - [ ] Load history on mount
  - [ ] Infinite scroll (load more)
  - [ ] Sync с БД (ChatHistory)

### Фаза 3: Backend API (Day 6-7)
- [ ] Market API:
  - [ ] `/api/market/fear-greed`
  - [ ] `/api/market/movers`
- [ ] Watchlist API:
  - [ ] CRUD endpoints
  - [ ] Database model `Watchlist`
  - [ ] Alembic migration
- [ ] Chat API:
  - [ ] `/api/chat/stream` (SSE)
  - [ ] `/api/chat/history`
  - [ ] `/api/chat/regenerate`
- [ ] Analytics API:
  - [ ] Интеграция с существующими сервисами
  - [ ] Агрегация данных

### Фаза 4: Analytics Page (Day 8-9)
- [ ] Создать `frontend/app/analytics/page.tsx`
- [ ] Symbol selector component
- [ ] Tabs implementation (Overview/Technicals/On-Chain/Sentiment)
- [ ] Indicators visualization:
  - [ ] RSI gauge
  - [ ] MACD chart
  - [ ] Bollinger Bands
  - [ ] Candlestick patterns list
- [ ] Charts library (lightweight-charts или recharts)

### Фаза 5: Referral Page (Day 10)
- [ ] Создать `frontend/app/referral/page.tsx`
- [ ] Компоненты:
  - [ ] `ReferralLinkCard.tsx`
  - [ ] `ReferralStatsCard.tsx`
  - [ ] `BalanceCard.tsx`
  - [ ] `LeaderboardCard.tsx`
  - [ ] `TierInfoModal.tsx`
- [ ] Share functionality (Telegram share)
- [ ] Copy to clipboard

### Фаза 6: Profile & Premium Purchase (Day 11-12)
- [ ] Создать `frontend/app/profile/page.tsx`
- [ ] Компоненты:
  - [ ] `UserProfileCard.tsx`
  - [ ] `SubscriptionSection.tsx`
  - [ ] `UpgradeCard.tsx`
  - [ ] `ActiveSubscriptionCard.tsx`
  - [ ] **`PurchaseModal.tsx`** - КЛЮЧЕВОЙ КОМПОНЕНТ
  - [ ] `UsageStatsCard.tsx`
  - [ ] `SettingsSection.tsx`
- [ ] Purchase flow:
  - [ ] Tier selection
  - [ ] Duration selection
  - [ ] **Payment method selector**
  - [ ] Telegram Stars integration
  - [ ] Balance payment option
- [ ] Settings:
  - [ ] Language switcher
  - [ ] Notifications toggle
  - [ ] Clear history
- [ ] Backend:
  - [ ] `/api/purchase/create-invoice`
  - [ ] `/api/purchase/with-balance`
  - [ ] Обработка successful_payment

### Фаза 7: Polish & Testing (Day 13-14)
- [ ] UX improvements:
  - [ ] Loading states
  - [ ] Error handling
  - [ ] Empty states
  - [ ] Skeleton loaders
- [ ] Animations:
  - [ ] Page transitions
  - [ ] Micro-interactions
  - [ ] Haptic feedback
- [ ] Testing:
  - [ ] Unit tests (компоненты)
  - [ ] Integration tests (API)
  - [ ] E2E tests (Playwright)
- [ ] Optimization:
  - [ ] Bundle size
  - [ ] Code splitting
  - [ ] Image optimization
  - [ ] Caching

### Фаза 8: Deployment (Day 15)
- [ ] Frontend:
  - [ ] Build production
  - [ ] Deploy to Vercel
  - [ ] Setup custom domain
- [ ] Backend:
  - [ ] Production environment variables
  - [ ] CORS setup
  - [ ] Rate limiting
- [ ] Bot integration:
  - [ ] Update /start handler с Web App кнопкой
  - [ ] Test full flow

---

## 📊 Прогресс-трекер

### Общий прогресс: 25% (2/8 фаз)

| Фаза | Задачи | Выполнено | Прогресс |
|------|--------|-----------|----------|
| **1. Frontend Foundation** | 4 | 4 | 100% ✅✅✅✅ |
| **2. Chat Implementation** | 6 | 6 | 100% ✅✅✅✅ |
| **3. Backend API** | 8 | 0 | 0% ⚪⚪⚪⚪ |
| **4. Analytics Page** | 6 | 0 | 0% ⚪⚪⚪⚪ |
| **5. Referral Page** | 6 | 0 | 0% ⚪⚪⚪⚪ |
| **6. Profile & Purchase** | 10 | 0 | 0% ⚪⚪⚪⚪ |
| **7. Polish & Testing** | 4 | 0 | 0% ⚪⚪⚪⚪ |
| **8. Deployment** | 6 | 0 | 0% ⚪⚪⚪⚪ |

### Текущая сессия:
**Начало**: 2025-01-18
**Статус**: Фаза 1 ✅ + Фаза 2 ✅ завершены!
**Следующий шаг**: Фаза 3 - Backend API endpoints

### Выполнено в этой сессии:

**Фаза 1: Frontend Foundation (100%)**
- ✅ Создан компонент FearGreedCard.tsx с анимированным индикатором
- ✅ Создан компонент WatchlistSection.tsx для избранных монет
- ✅ Создан компонент TopMoversSection.tsx (gainers/losers)
- ✅ Обновлен Home page (app/page.tsx) - убран мусор (balance, trades), добавлены новые компоненты

**Фаза 2: Chat Implementation (100%)** 🎉
- ✅ Установлены зависимости: react-markdown, remark-gfm, react-syntax-highlighter
- ✅ Создан компонент ChatMessage.tsx с markdown рендерингом и подсветкой синтаксиса
- ✅ Создан компонент TypingIndicator.tsx с плавной анимацией
- ✅ Создан компонент MessageList.tsx с auto-scroll и welcome screen
- ✅ Создан компонент ChatInput.tsx с suggested prompts и индикатором лимитов
- ✅ Создана Chat page (app/chat/page.tsx) с интеграцией всех компонентов
- ✅ Обновлен Header компонент - добавлена поддержка кастомных заголовков и кнопки назад
- ✅ Исправлены TypeScript ошибки (useEffect setState, HTML entities)

---

## 📚 Технологии

### Frontend Stack:
```json
{
  "framework": "Next.js 15",
  "language": "TypeScript 5",
  "styling": "Tailwind CSS v4",
  "animations": "Framer Motion 12",
  "telegram-sdk": "@telegram-apps/sdk",
  "state": "Zustand 5",
  "i18n": "next-intl 4",
  "markdown": "react-markdown + remark-gfm",
  "syntax-highlighting": "react-syntax-highlighter",
  "charts": "lightweight-charts",
  "http": "axios"
}
```

### Backend Stack:
```json
{
  "framework": "FastAPI",
  "database": "PostgreSQL + SQLAlchemy 2.0",
  "auth": "Telegram initData validation",
  "payments": "Telegram Stars, TON Connect (future)",
  "ai": "OpenAI GPT-4o/GPT-4o-mini"
}
```

---

## 🎯 Ключевые моменты

### Design Principles:
1. **Chat-first** - чат это главная фишка, 50% времени на него
2. **Apple-level polish** - плавные анимации, glassmorphism, attention to detail
3. **Mobile-first** - оптимизация под телефоны
4. **Fast & responsive** - мгновенная обратная связь
5. **Accessible** - понятный UX для всех

### Performance Goals:
- First Contentful Paint: < 1.5s
- Time to Interactive: < 3s
- Bundle size: < 500KB (gzipped)
- Chat response latency: < 500ms

### Security:
- ✅ Telegram initData validation
- ✅ HTTPS only
- ✅ CORS configured
- ✅ Rate limiting
- ✅ Input sanitization

---

**Создано**: 2025-01-18
**Последнее обновление**: 2025-01-18
**Версия плана**: 1.0.0

🚀 **Ready to build!**
