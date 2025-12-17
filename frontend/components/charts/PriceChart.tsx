/**
 * PriceChart Component
 * Интерактивный график цены криптовалюты с использованием lightweight-charts
 */

'use client';

import { useEffect, useRef } from 'react';
import {
  createChart,
  ColorType,
  IChartApi,
  ISeriesApi,
  AreaSeries
} from 'lightweight-charts';

interface PriceData {
  time: number;
  value: number;
}

type ChartData = {
  time: number;
  value: number;
};

interface PriceChartProps {
  data: PriceData[];
  isPositive?: boolean;
  height?: number;
}

export default function PriceChart({ data, isPositive = true, height = 300 }: PriceChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current || data.length === 0) return;

    // Создаем график
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#9CA3AF',
        fontSize: 12,
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
      },
      crosshair: {
        mode: 1,
        vertLine: {
          color: '#3B82F6',
          width: 1,
          style: 2,
          labelBackgroundColor: '#3B82F6',
        },
        horzLine: {
          color: '#3B82F6',
          width: 1,
          style: 2,
          labelBackgroundColor: '#3B82F6',
        },
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
        timeVisible: true,
        secondsVisible: false,
      },
      width: chartContainerRef.current.clientWidth,
      height: height,
    });

    // Создаем area series (используем современный API)
    const areaSeries = chart.addSeries(AreaSeries, {
      topColor: isPositive ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)',
      bottomColor: isPositive ? 'rgba(34, 197, 94, 0.0)' : 'rgba(239, 68, 68, 0.0)',
      lineColor: isPositive ? '#22C55E' : '#EF4444',
      lineWidth: 2,
      priceLineVisible: false,
    });

    // Устанавливаем данные (преобразуем в формат lightweight-charts)
    const chartData = data.map(item => ({
      time: item.time as any, // Приводим к типу Time
      value: item.value
    }));
    areaSeries.setData(chartData);

    // Автоматически подгоняем график под данные
    chart.timeScale().fitContent();

    chartRef.current = chart;
    seriesRef.current = areaSeries;

    // Обработчик ресайза
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, [data, isPositive, height]);

  return (
    <div
      ref={chartContainerRef}
      className="w-full overflow-hidden"
      style={{
        height: `${height}px`,
        minHeight: `${height}px`,
        maxHeight: `${height}px`,
      }}
    />
  );
}
