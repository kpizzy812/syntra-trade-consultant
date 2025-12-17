# Fraud Detection Integration Guide

## Overview

Система обнаружения fraud включает:
1. **Multi-trial abuse** - блокировка повторных trial при регистрации через telegram + email
2. **Self-referral abuse** - блокировка самореферала (один человек с 2 аккаунтами)
3. **Linked accounts tracking** - отслеживание связанных аккаунтов для админки

## Backend Architecture

### Database Models

```python
# src/database/models.py

DeviceFingerprint  # Хранит IP, fingerprint, device info для каждого пользователя
LinkedAccount      # Связи между подозрительными аккаунтами
```

### Services

```python
# src/services/fraud_detection_service.py

save_device_fingerprint()     # Сохранить fingerprint при login/registration
check_for_existing_trial()    # Проверить есть ли trial у связанных аккаунтов
check_self_referral()         # Проверить self-referral abuse
detect_and_link_accounts()    # Найти и связать похожие аккаунты
```

### API Endpoints

```
# Fraud Admin API (только для админов)
GET  /api/admin/fraud/summary                    # Статистика abuse
GET  /api/admin/fraud/linked-accounts            # Список связанных аккаунтов
GET  /api/admin/fraud/linked-accounts/{id}       # Детали связи
PUT  /api/admin/fraud/linked-accounts/{id}/status # Обновить статус
POST /api/admin/fraud/linked-accounts/{id}/ban   # Забанить аккаунты
GET  /api/admin/fraud/users/{id}/fingerprints    # Fingerprints пользователя
GET  /api/admin/fraud/users/{id}/linked-accounts # Связанные аккаунты юзера
```

---

## Frontend Integration

### 1. Install FingerprintJS (Pro recommended)

```bash
npm install @fingerprintjs/fingerprintjs-pro
# или бесплатная версия (менее точная):
npm install @fingerprintjs/fingerprintjs
```

### 2. Create Fingerprint Hook

```typescript
// frontend/hooks/useFingerprint.ts
import { useState, useEffect } from 'react';

interface FingerprintData {
  visitorId: string | null;
  fingerprintHash: string | null;
  screenResolution: string;
  timezone: string;
  language: string;
}

export function useFingerprint(): FingerprintData {
  const [data, setData] = useState<FingerprintData>({
    visitorId: null,
    fingerprintHash: null,
    screenResolution: `${window.screen.width}x${window.screen.height}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: navigator.language,
  });

  useEffect(() => {
    const loadFingerprint = async () => {
      try {
        // Option 1: FingerprintJS Pro (более точный)
        // const FingerprintJS = await import('@fingerprintjs/fingerprintjs-pro');
        // const fp = await FingerprintJS.load({ apiKey: 'your-api-key' });
        // const result = await fp.get();
        // setData(prev => ({ ...prev, visitorId: result.visitorId }));

        // Option 2: FingerprintJS Open Source (бесплатно)
        const FingerprintJS = await import('@fingerprintjs/fingerprintjs');
        const fp = await FingerprintJS.load();
        const result = await fp.get();

        setData(prev => ({
          ...prev,
          visitorId: result.visitorId,
          fingerprintHash: result.visitorId, // В OSS версии это hash
        }));
      } catch (error) {
        console.error('Failed to load fingerprint:', error);
        // Fallback: создаем кастомный hash из доступных данных
        const customHash = await createCustomFingerprint();
        setData(prev => ({ ...prev, fingerprintHash: customHash }));
      }
    };

    loadFingerprint();
  }, []);

  return data;
}

// Кастомный fingerprint как fallback
async function createCustomFingerprint(): Promise<string> {
  const components = [
    navigator.userAgent,
    navigator.language,
    screen.width + 'x' + screen.height,
    screen.colorDepth,
    new Date().getTimezoneOffset(),
    navigator.hardwareConcurrency || 0,
    navigator.deviceMemory || 0,
  ].join('|');

  // SHA-256 hash
  const encoder = new TextEncoder();
  const data = encoder.encode(components);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}
```

### 3. Integrate in Auth Flow

```typescript
// frontend/app/auth/verify/page.tsx
'use client';

import { useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useFingerprint } from '@/hooks/useFingerprint';

export default function VerifyMagicLink() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get('token');
  const fingerprint = useFingerprint();

  useEffect(() => {
    if (!token || !fingerprint.visitorId) return;

    const verifyToken = async () => {
      try {
        const response = await fetch('/api/auth/magic/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            token,
            visitor_id: fingerprint.visitorId,
            fingerprint_hash: fingerprint.fingerprintHash,
            screen_resolution: fingerprint.screenResolution,
            timezone: fingerprint.timezone,
            language: fingerprint.language,
          }),
        });

        const data = await response.json();

        if (data.success) {
          // Сохраняем JWT token
          localStorage.setItem('auth_token', data.token);

          // Показываем предупреждение если trial заблокирован
          if (data.trial_blocked) {
            alert(data.abuse_warning || 'Trial не доступен для этого устройства');
          }

          router.push('/home');
        } else {
          alert('Ошибка авторизации: ' + data.detail);
          router.push('/auth/login');
        }
      } catch (error) {
        console.error('Verification failed:', error);
        router.push('/auth/login');
      }
    };

    verifyToken();
  }, [token, fingerprint.visitorId]);

  return <div>Verifying...</div>;
}
```

### 4. Integrate in Referral Flow

```typescript
// frontend/components/ReferralApply.tsx
'use client';

import { useState } from 'react';
import { useFingerprint } from '@/hooks/useFingerprint';

interface Props {
  onSuccess: () => void;
}

export function ReferralApply({ onSuccess }: Props) {
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fingerprint = useFingerprint();

  const applyReferral = async () => {
    if (!code.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/referral/apply', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
        body: JSON.stringify({
          referral_code: code.toUpperCase(),
          visitor_id: fingerprint.visitorId,
          fingerprint_hash: fingerprint.fingerprintHash,
        }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        alert(`Реферал применен! Приглашён: ${data.referrer_name}`);
        onSuccess();
      } else {
        setError(data.detail || 'Не удалось применить реферал');
      }
    } catch (err) {
      setError('Ошибка сети');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <input
        value={code}
        onChange={(e) => setCode(e.target.value)}
        placeholder="Введите реферальный код"
      />
      <button onClick={applyReferral} disabled={loading}>
        {loading ? 'Применяю...' : 'Применить'}
      </button>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
```

---

## Admin Panel Integration

### Linked Accounts Dashboard

```typescript
// frontend/app/admin/fraud/page.tsx
'use client';

import { useEffect, useState } from 'react';

interface LinkedAccount {
  id: number;
  link_type: string;
  confidence_score: number;
  status: string;
  user_a: { id: number; email: string; telegram_id: number };
  user_b: { id: number; email: string; telegram_id: number };
  shared_ips: string[];
  shared_visitor_ids: string[];
}

export default function FraudAdmin() {
  const [links, setLinks] = useState<LinkedAccount[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/admin/fraud/linked-accounts?min_confidence=0.5', {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
      },
    })
      .then((res) => res.json())
      .then((data) => {
        setLinks(data);
        setLoading(false);
      });
  }, []);

  const updateStatus = async (id: number, status: string) => {
    await fetch(`/api/admin/fraud/linked-accounts/${id}/status`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
      },
      body: JSON.stringify({ status }),
    });
    // Refresh list
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <h1>Fraud Detection - Linked Accounts</h1>
      <table>
        <thead>
          <tr>
            <th>Type</th>
            <th>Confidence</th>
            <th>User A</th>
            <th>User B</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {links.map((link) => (
            <tr key={link.id}>
              <td>{link.link_type}</td>
              <td>{(link.confidence_score * 100).toFixed(0)}%</td>
              <td>{link.user_a?.email || link.user_a?.telegram_id}</td>
              <td>{link.user_b?.email || link.user_b?.telegram_id}</td>
              <td>{link.status}</td>
              <td>
                <button onClick={() => updateStatus(link.id, 'confirmed_abuse')}>
                  Confirm Abuse
                </button>
                <button onClick={() => updateStatus(link.id, 'false_positive')}>
                  False Positive
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## Confidence Score Logic

| Signal | Confidence |
|--------|------------|
| Same IP only | 0.4 (50%) |
| Same FingerprintJS visitor_id | 0.9 (high) |
| Same custom fingerprint hash | 0.7 (medium) |
| IP + fingerprint match | 0.95+ |

### Thresholds

- **< 0.5** - Ignore (likely false positive)
- **0.5-0.7** - Monitor (possible abuse)
- **> 0.7** - Block action (likely abuse)

---

## Testing

```bash
# Run fraud detection tests
pytest tests/test_fraud_detection.py -v
```

### Test Scenarios

1. **Multi-trial test**: Register via telegram, then same IP via email
2. **Self-referral test**: Create referral, use from same browser
3. **False positive test**: Different users from same office/VPN

---

## Environment Variables

```bash
# Optional: FingerprintJS Pro API key
FINGERPRINT_API_KEY=your-api-key

# Confidence thresholds (defaults)
FRAUD_CONFIDENCE_HIGH=0.9
FRAUD_CONFIDENCE_MEDIUM=0.7
FRAUD_CONFIDENCE_LOW=0.5

# Time windows (days)
FRAUD_IP_MATCH_WINDOW=30
FRAUD_FINGERPRINT_MATCH_WINDOW=90
```
