/**
 * Hook для работы с TON Connect платежами
 *
 * Поддерживает:
 * - Нативные TON переводы
 * - USDT (Jetton) переводы на TON blockchain
 * - Подключение/отключение кошелька
 *
 * Адаптировано из Tradient AI для Syntra Trade Consultant
 */

'use client';

import { useState, useCallback } from 'react';
import { useTonConnectUI, useTonAddress, useTonWallet } from '@tonconnect/ui-react';
import toast from 'react-hot-toast';

interface SendPaymentParams {
  address: string;      // Адрес получателя
  amount: number;       // Сумма (TON или USDT)
  memo?: string;        // Комментарий для идентификации
  currency?: 'ton' | 'usdt';  // Валюта (по умолчанию TON)
}

interface SendPaymentResult {
  success: boolean;
  boc?: string;         // Bag of Cells (подтверждение транзакции)
  error?: string;
}

export function useTonPayment() {
  const [tonConnectUI] = useTonConnectUI();
  const walletAddress = useTonAddress();
  const wallet = useTonWallet();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Отправка TON платежа
   */
  const sendTonPayment = useCallback(
    async ({ address, amount, memo }: SendPaymentParams): Promise<SendPaymentResult> => {
      setIsLoading(true);
      setError(null);

      try {
        // Проверка подключения
        if (!wallet) {
          throw new Error('Кошелек не подключен. Подключите TON кошелек.');
        }

        // Динамический импорт @ton/ton (только на клиенте, избегаем SSR)
        const { beginCell } = await import('@ton/ton');

        // Конвертация TON в nanotons (1 TON = 1_000_000_000 nanotons)
        const amountInNanotons = Math.floor(amount * 1_000_000_000).toString();

        // Создаем payload с текстовым комментарием если есть memo
        let payloadBase64: string | undefined;
        if (memo) {
          const body = beginCell()
            .storeUint(0, 32)                    // Opcode 0x00000000 = текстовый комментарий
            .storeStringTail(memo)               // Текст комментария
            .endCell();
          payloadBase64 = body.toBoc().toString('base64');
        }

        // Формирование транзакции
        const transaction = {
          validUntil: Math.floor(Date.now() / 1000) + 600, // 10 минут на подтверждение
          messages: [
            {
              address,
              amount: amountInNanotons,
              // Payload в формате base64 encoded Cell
              ...(payloadBase64 && { payload: payloadBase64 }),
            },
          ],
        };

        console.log('📤 Отправка TON транзакции:', {
          to: address,
          amount: `${amount} TON`,
          memo,
          wallet: wallet.device?.appName || 'TON Wallet',
        });

        // Отправка через TON Connect UI
        const result = await tonConnectUI.sendTransaction(transaction);

        console.log('✅ Транзакция отправлена:', result);

        toast.success(`Транзакция отправлена! ${amount} TON`);

        return {
          success: true,
          boc: result.boc,
        };
      } catch (err: any) {
        console.error('❌ Ошибка отправки TON:', err);

        let errorMessage = 'Ошибка при отправке платежа';

        // Обработка типичных ошибок
        if (err.message?.includes('User rejected')) {
          errorMessage = 'Вы отменили транзакцию';
        } else if (err.message?.includes('Insufficient funds')) {
          errorMessage = 'Недостаточно средств на балансе';
        } else if (err.message?.includes('Network')) {
          errorMessage = 'Ошибка сети. Проверьте подключение';
        } else if (err.message) {
          errorMessage = err.message;
        }

        setError(errorMessage);
        toast.error(errorMessage);

        return {
          success: false,
          error: errorMessage,
        };
      } finally {
        setIsLoading(false);
      }
    },
    [tonConnectUI, wallet]
  );

  /**
   * Отправка USDT (Jetton) платежа
   * USDT на TON использует jetton transfer стандарт (TEP-74)
   */
  const sendUsdtPayment = useCallback(
    async ({ address, amount, memo }: SendPaymentParams): Promise<SendPaymentResult> => {
      setIsLoading(true);
      setError(null);

      try {
        if (!wallet || !walletAddress) {
          throw new Error('Кошелек не подключен');
        }

        // Динамический импорт @ton/ton
        const { Address, beginCell, toNano } = await import('@ton/ton');

        // USDT Jetton Master на mainnet
        const USDT_JETTON_MASTER = 'EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs';

        // Конвертация USDT в микро-единицы (USDT имеет 6 decimals)
        const amountInMicro = BigInt(Math.floor(amount * 1_000_000));

        // Вычисляем jetton wallet адрес пользователя
        // Используем TonClient для on-chain запроса
        const { TonClient } = await import('@ton/ton');
        const client = new TonClient({
          endpoint: 'https://toncenter.com/api/v2/jsonRPC',
        });

        const jettonMasterAddress = Address.parse(USDT_JETTON_MASTER);
        const ownerAddress = Address.parse(walletAddress);

        // Вызов get_wallet_address метода jetton master контракта
        const { stack } = await client.runMethod(jettonMasterAddress, 'get_wallet_address', [
          { type: 'slice', cell: beginCell().storeAddress(ownerAddress).endCell() },
        ]);

        const userJettonWalletAddress = stack.readAddress();

        // Построение jetton transfer body согласно TEP-74
        // https://github.com/ton-blockchain/TEPs/blob/master/text/0074-jettons-standard.md
        const jettonTransferBody = beginCell()
          .storeUint(0xf8a7ea5, 32)                           // jetton transfer op code
          .storeUint(0, 64)                                   // query_id
          .storeCoins(amountInMicro)                          // jetton amount
          .storeAddress(Address.parse(address))               // destination
          .storeAddress(Address.parse(walletAddress))         // response destination (для excess)
          .storeBit(0)                                        // custom payload (null)
          .storeCoins(toNano('0.05'))                         // forward amount (0.05 TON)
          .storeBit(1)                                        // forward payload в ref
          .storeRef(
            beginCell()
              .storeUint(0, 32)                               // text comment opcode
              .storeStringTail(memo || '')                    // comment/memo
              .endCell()
          )
          .endCell();

        console.log('📤 Отправка USDT jetton транзакции:', {
          to: address,
          amount: `${amount} USDT`,
          memo,
          jettonWallet: userJettonWalletAddress.toString(),
        });

        // Отправляем транзакцию на jetton wallet адрес пользователя
        const transaction = {
          validUntil: Math.floor(Date.now() / 1000) + 600,
          messages: [
            {
              address: userJettonWalletAddress.toString(),
              amount: toNano('0.1').toString(),  // Газ для jetton transfer (~0.1 TON)
              payload: jettonTransferBody.toBoc().toString('base64'),
            },
          ],
        };

        const result = await tonConnectUI.sendTransaction(transaction);

        console.log('✅ USDT транзакция отправлена:', result);

        toast.success(`USDT транзакция отправлена! ${amount} USDT`);

        return {
          success: true,
          boc: result.boc,
        };
      } catch (err: any) {
        console.error('❌ Ошибка отправки USDT:', err);

        let errorMessage = 'Ошибка при отправке USDT';

        if (err.message?.includes('User rejected')) {
          errorMessage = 'Вы отменили транзакцию';
        } else if (err.message?.includes('Insufficient funds')) {
          errorMessage = 'Недостаточно средств (нужно ~0.1 TON для газа + USDT)';
        } else if (err.message) {
          errorMessage = err.message;
        }

        setError(errorMessage);
        toast.error(errorMessage);

        return {
          success: false,
          error: errorMessage,
        };
      } finally {
        setIsLoading(false);
      }
    },
    [tonConnectUI, wallet, walletAddress]
  );

  /**
   * Подключение кошелька
   */
  const connectWallet = useCallback(async () => {
    try {
      await tonConnectUI.openModal();
    } catch (err) {
      console.error('Ошибка подключения кошелька:', err);
      toast.error('Не удалось открыть модалку подключения');
    }
  }, [tonConnectUI]);

  /**
   * Отключение кошелька
   */
  const disconnectWallet = useCallback(async () => {
    try {
      await tonConnectUI.disconnect();
      toast.success('Кошелек отключен');
    } catch (err) {
      console.error('Ошибка отключения:', err);
      toast.error('Не удалось отключить кошелек');
    }
  }, [tonConnectUI]);

  return {
    // Функции
    sendTonPayment,
    sendUsdtPayment,
    connectWallet,
    disconnectWallet,

    // Состояние
    isLoading,
    error,
    isConnected: !!wallet,
    walletAddress,
    wallet,
  };
}
