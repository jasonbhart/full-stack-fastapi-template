import { Box, Flex, Icon, Text } from "@chakra-ui/react"
import { useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import {
  FiBriefcase,
  FiHome,
  FiMessageSquare,
  FiSettings,
  FiUsers,
} from "react-icons/fi"
import type { IconType } from "react-icons/lib"

import type { UserPublic } from "@/client"
import { features } from "@/config/features"

const items = [
  { icon: FiHome, title: "Dashboard", path: "/" },
  { icon: FiBriefcase, title: "Items", path: "/items" },
  { icon: FiSettings, title: "User Settings", path: "/settings" },
]

// Agent menu item - only included when feature flag is enabled
const agentItem = {
  icon: FiMessageSquare,
  title: "AI Assistant",
  path: "/agent",
}

interface SidebarItemsProps {
  onClose?: () => void
}

interface Item {
  icon: IconType
  title: string
  path: string
}

const SidebarItems = ({ onClose }: SidebarItemsProps) => {
  const queryClient = useQueryClient()
  const currentUser = queryClient.getQueryData<UserPublic>(["currentUser"])

  // Build menu items with feature flags and role-based access
  let finalItems: Item[] = [...items]

  // Add agent item if feature is enabled
  if (features.agent) {
    finalItems = [...finalItems, agentItem]
  }

  // Add admin item for superusers
  if (currentUser?.is_superuser) {
    finalItems = [
      ...finalItems,
      { icon: FiUsers, title: "Admin", path: "/admin" },
    ]
  }

  const listItems = finalItems.map(({ icon, title, path }) => (
    <RouterLink key={title} to={path} onClick={onClose}>
      <Flex
        gap={4}
        px={4}
        py={2}
        _hover={{
          background: "gray.subtle",
        }}
        alignItems="center"
        fontSize="sm"
      >
        <Icon as={icon} alignSelf="center" />
        <Text ml={2}>{title}</Text>
      </Flex>
    </RouterLink>
  ))

  return (
    <>
      <Text fontSize="xs" px={4} py={2} fontWeight="bold">
        Menu
      </Text>
      <Box>{listItems}</Box>
    </>
  )
}

export default SidebarItems
