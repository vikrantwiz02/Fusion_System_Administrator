import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Flex,
  Title,
  Table,
  TextInput,
  Select,
  Badge,
  Text,
  ScrollArea,
  Loader,
  Center,
  rem,
} from '@mantine/core';
import { showNotification } from '@mantine/notifications';
import { FaTimes, FaSync } from 'react-icons/fa';
import { fetchAuditLogs } from '../../api/Roles';

const ACTION_COLORS = {
  CREATE: 'green',
  UPDATE: 'blue',
  DELETE: 'red',
  RESET_PASSWORD: 'orange',
  BULK_IMPORT: 'violet',
  ROLE_CHANGE: 'cyan',
  MODULE_ACCESS_CHANGE: 'yellow',
};

const ACTION_OPTIONS = [
  { value: '', label: 'All Actions' },
  { value: 'CREATE', label: 'Create' },
  { value: 'UPDATE', label: 'Update' },
  { value: 'DELETE', label: 'Delete' },
  { value: 'RESET_PASSWORD', label: 'Reset Password' },
  { value: 'BULK_IMPORT', label: 'Bulk Import' },
  { value: 'ROLE_CHANGE', label: 'Role Change' },
  { value: 'MODULE_ACCESS_CHANGE', label: 'Module Access Change' },
];

const AuditLogPage = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actorFilter, setActorFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [resourceFilter, setResourceFilter] = useState('');

  const xIcon = <FaTimes style={{ width: rem(20), height: rem(20) }} />;

  const loadLogs = async () => {
    setLoading(true);
    try {
      const filters = {};
      if (actorFilter) filters.actor = actorFilter;
      if (actionFilter) filters.action = actionFilter;
      if (resourceFilter) filters.resource_type = resourceFilter;
      const data = await fetchAuditLogs(filters);
      setLogs(data);
    } catch (err) {
      showNotification({
        title: 'Error',
        icon: xIcon,
        position: 'top-center',
        withCloseButton: true,
        message: 'Failed to load audit logs.',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  const formatTimestamp = (ts) => {
    const d = new Date(ts);
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDetails = (details) => {
    if (!details || Object.keys(details).length === 0) return '—';
    return Object.entries(details)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') || 'none' : v}`)
      .join(' | ');
  };

  const rows = logs.map((log) => (
    <Table.Tr key={log.id}>
      <Table.Td style={{ whiteSpace: 'nowrap', fontSize: '0.8rem' }}>
        {formatTimestamp(log.timestamp)}
      </Table.Td>
      <Table.Td>
        <Text fw={600} size="sm">{log.actor}</Text>
      </Table.Td>
      <Table.Td>
        <Badge color={ACTION_COLORS[log.action] || 'gray'} variant="light">
          {log.action}
        </Badge>
      </Table.Td>
      <Table.Td>
        <Text size="sm" c="dimmed">{log.resource_type}</Text>
      </Table.Td>
      <Table.Td>
        <Text size="sm">{log.target_user || '—'}</Text>
      </Table.Td>
      <Table.Td style={{ maxWidth: 300, fontSize: '0.8rem', color: '#555' }}>
        {formatDetails(log.details)}
      </Table.Td>
      <Table.Td>
        <Text size="xs" c="dimmed">{log.ip_address || '—'}</Text>
      </Table.Td>
    </Table.Tr>
  ));

  return (
    <Box style={{ padding: '1.5rem' }}>
      <Flex justify="center" mb="xl">
        <Button
          variant="gradient"
          size="xl"
          radius="xs"
          gradient={{ from: 'blue', to: 'cyan', deg: 90 }}
          style={{ fontSize: '1.8rem', lineHeight: 1.2, pointerEvents: 'none' }}
        >
          <Title order={1} style={{ fontSize: '1.25rem', wordBreak: 'break-word' }}>
            Audit Log
          </Title>
        </Button>
      </Flex>

      {/* Filters */}
      <Flex gap="md" mb="md" wrap="wrap" align="flex-end">
        <TextInput
          label="Filter by Admin"
          placeholder="e.g. admin1"
          value={actorFilter}
          onChange={(e) => setActorFilter(e.target.value)}
          style={{ flex: 1, minWidth: 160 }}
        />
        <Select
          label="Filter by Action"
          data={ACTION_OPTIONS}
          value={actionFilter}
          onChange={(v) => setActionFilter(v || '')}
          style={{ flex: 1, minWidth: 160 }}
        />
        <TextInput
          label="Filter by Resource"
          placeholder="e.g. student"
          value={resourceFilter}
          onChange={(e) => setResourceFilter(e.target.value)}
          style={{ flex: 1, minWidth: 160 }}
        />
        <Button leftSection={<FaSync />} onClick={loadLogs} loading={loading}>
          Apply
        </Button>
      </Flex>

      {loading ? (
        <Center mt="xl"><Loader /></Center>
      ) : logs.length === 0 ? (
        <Center mt="xl"><Text c="dimmed">No audit log entries found.</Text></Center>
      ) : (
        <ScrollArea>
          <Table striped highlightOnHover withTableBorder withColumnBorders>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Time</Table.Th>
                <Table.Th>Admin</Table.Th>
                <Table.Th>Action</Table.Th>
                <Table.Th>Resource</Table.Th>
                <Table.Th>Affected User</Table.Th>
                <Table.Th>Details</Table.Th>
                <Table.Th>IP Address</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>{rows}</Table.Tbody>
          </Table>
        </ScrollArea>
      )}
    </Box>
  );
};

export default AuditLogPage;
