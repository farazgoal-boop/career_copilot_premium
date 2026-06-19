import React from 'react';
import {StyleSheet, Text, View} from 'react-native';

import {LiveBridgeEnvelope, MobileBridgeSnapshot} from '../types';

type BubbleCardProps = {
  overlay: LiveBridgeEnvelope['overlay'];
  session: MobileBridgeSnapshot;
};

export function BubbleCard({overlay, session}: BubbleCardProps): React.JSX.Element {
  return (
    <View style={styles.card}>
      <View style={styles.row}>
        <Text style={styles.company}>{session.company_name}</Text>
        <Text style={styles.badge}>{overlay.status}</Text>
      </View>
      <Text style={styles.role}>{session.role_title}</Text>
      <Text style={styles.headline}>{overlay.headline}</Text>
      <Text style={styles.body}>{overlay.body}</Text>
      <View style={styles.metaRow}>
        <Text style={styles.meta}>Confidence {overlay.confidence_score}%</Text>
        <Text style={styles.meta}>{session.worker_status}</Text>
      </View>
      {overlay.alternatives.length > 0 ? (
        <View style={styles.altWrap}>
          {overlay.alternatives.map(item => (
            <Text key={item} style={styles.altItem}>
              {item}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#f1ede4',
    borderRadius: 24,
    gap: 10,
    padding: 18,
  },
  row: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  company: {
    color: '#14212a',
    fontSize: 18,
    fontWeight: '800',
  },
  badge: {
    backgroundColor: '#14212a',
    borderRadius: 999,
    color: '#f3f7fa',
    overflow: 'hidden',
    paddingHorizontal: 10,
    paddingVertical: 4,
    textTransform: 'uppercase',
  },
  role: {
    color: '#50606a',
    fontSize: 14,
    fontWeight: '600',
  },
  headline: {
    color: '#14212a',
    fontSize: 20,
    fontWeight: '800',
  },
  body: {
    color: '#24343d',
    fontSize: 15,
    lineHeight: 22,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  meta: {
    color: '#4f5d65',
    fontSize: 13,
    fontWeight: '600',
  },
  altWrap: {
    gap: 8,
  },
  altItem: {
    color: '#30434d',
    fontSize: 13,
  },
});