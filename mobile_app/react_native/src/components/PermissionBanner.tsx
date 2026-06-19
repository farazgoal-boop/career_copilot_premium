import React from 'react';
import {StyleSheet, Text, View} from 'react-native';

type PermissionBannerProps = {
  message: string;
  overlayRunning: boolean;
};

export function PermissionBanner({message, overlayRunning}: PermissionBannerProps): React.JSX.Element {
  return (
    <View style={[styles.banner, overlayRunning ? styles.running : styles.idle]}>
      <Text style={styles.title}>{overlayRunning ? 'Bubble overlay active' : 'Bubble overlay standby'}</Text>
      <Text style={styles.body}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    borderRadius: 18,
    gap: 6,
    padding: 16,
  },
  running: {
    backgroundColor: '#143428',
  },
  idle: {
    backgroundColor: '#3d2618',
  },
  title: {
    color: '#f7fbfd',
    fontSize: 16,
    fontWeight: '800',
  },
  body: {
    color: '#dbe5ea',
    lineHeight: 21,
  },
});