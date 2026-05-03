![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Autodesk Maya](https://img.shields.io/badge/Autodesk%20Maya-37A5CC?style=for-the-badge)

# OrientAimUp Tool for Autodesk Maya

---

## Overview

**OrientAimUp** is a lightweight Maya utility for creating temporary **Aim**, **Orient**, and **World Up** locators, then using those locators to quickly orient an object with an aim-style setup.

The tool is designed for artists who need a simple visual way to define direction:

- **Aim** locator: where the object should look
- **World Up** locator: how the object should keep its up direction
- **Orient** object / locator: the object that receives the orientation

This makes it easier to build clean orientation references for props, controls, helper locators, facial points, rigging markers, or manual alignment tasks without manually calculating vector direction.

> ⚠️ This tool is intended as an artist-friendly helper for orientation setup inside Autodesk Maya. Please check the result visually before publishing rig or animation data.

---

## Main Features

- Create locator helpers from selected **objects**, **vertices**, **edges**, or **faces**
- Supports three locator roles: `aimUp`, `orient`, and `worldUp`
- Uses selection context to decide how the locator should be placed
- Can place locators at transform pivots, vertex positions, edge centers, or face centers
- Single-face, two-vertex, three-vertex, and edge selections can generate oriented locator matrices
- Allows Aim Axis and Up Axis selection using simple X / Y / Z buttons
- Supports reverse direction for Aim and Up vectors
- Can orient an object using **Aim + Up + Orient** selection order
- Optional temporary constraint cleanup using **REMOVE_CONSTRAINT**
- Includes a menu launcher for the external **JAMMSoft Joint Orient Tool**

---

## Tool Buttons

### AIMUP

Creates an `aimUp` locator from the current selection.

Use this locator as the object or point that the final orient object should aim toward.

> This locator uses a fixed name per source object. If the same `aimUp` locator already exists, the tool will warn you instead of creating another one.

---

### ORIENT

Creates an `orient` locator from the current selection.

Use this when you need a target object that will receive the final orientation, or when you want to create an orientation reference from a component selection.

> This button allows multiple orient locators. If one already exists, the tool will create a numbered version such as `object_orient1`, `object_orient2`, etc.

---

### WORLDUP

Creates a `worldUp` locator from the current selection.

Use this locator to control the up direction when orienting the final object.

> This locator uses a fixed name per source object. If the same `worldUp` locator already exists, the tool will warn you instead of creating another one.

---

## Locator Creation Workflow

### From Object Selection

1. Select one or more transform objects
2. Click **AIMUP**, **ORIENT**, or **WORLDUP**
3. The locator is created at the average pivot position
4. For a single object selection, the locator tries to match the source object rotation

Good for:

- control alignment
- prop orientation reference
- general rigging helper locator placement

---

### From Vertex Selection

Select vertex components, then create a locator.

Behaviour:

- **1 vertex**: locator is placed directly on that vertex
- **2 vertices**: locator is placed between both vertices and aims along the vertex direction
- **3 vertices**: locator uses the three points to build an orientation plane
- **More than 3 vertices**: locator is placed at the average center

Good for:

- facial rig points
- surface landmark placement
- matching locator position to mesh detail

---

### From Edge Selection

Select one or more edges, then create a locator.

The tool calculates edge positions, edge direction, and mesh normals where possible, then builds a locator orientation from that information.

Good for:

- placing helpers along loops
- matching direction from mesh topology
- building quick tangent-based alignment references

---

### From Face Selection

Select face components, then create a locator.

Behaviour:

- **Single face**: locator is placed at the face center and oriented from the face normal and edge direction
- **Multiple faces**: locator is placed at the average face center

Good for:

- placing locators on flat surfaces
- orienting helpers from mesh normals
- surface-based rigging guides

---

## Orient Selection Workflow

Use this section when you already have three objects or locators and want to orient one object toward another.

### Selection Order

Select exactly **three objects** in this order:

```text
1. AIM object
2. UP object
3. ORIENT object
```

Then click:

```text
- Orient Selection -
```

The third selected object receives the orientation.

---

## Aim / Up Axis Settings

### Aim

The **Aim** row controls which local axis of the orient object should point toward the selected Aim object.

Available options:

- X
- Y
- Z
- Reverse

Example:

```text
Aim: X
```

means the orient object's local X axis will look toward the Aim object.

---

### Up

The **Up** row controls which local axis of the orient object should follow the World Up object.

Available options:

- X
- Y
- Z
- Reverse

Example:

```text
Up: Y
```

means the orient object's local Y axis will try to stay aligned to the World Up direction.

---

## REMOVE_CONSTRAINT Option

### Enabled

When **REMOVE_CONSTRAINT** is enabled, the tool creates a temporary aim constraint, applies the orientation, then deletes the constraint.

Use this when you only want the final orientation result and do not want to keep live constraints in the scene.

### Disabled

When **REMOVE_CONSTRAINT** is disabled, the aim constraint remains in the scene.

Use this when you want the orient object to keep following the Aim and World Up objects interactively.

---

## Automation Checkbox

The **AUTOMATION** checkbox is currently disabled.

The active artist workflow is the manual three-object selection mode:

```text
AIM → UP → ORIENT
```

---

## JAMMSoft Joint Orient Tool

The tool includes a menu entry:

```text
File > JAMMSoft JointOrient
```

This opens the bundled **JAMMSoft Joint Orient Tool**, which is useful when you need a more complete joint-orientation interface for skeleton work.

JAMMSoft supports workflows such as:

- orienting selected joints or full joint hierarchies
- choosing Aim and Up axis
- setting World Up direction
- guessing up direction
- orienting a joint to match another object
- orienting joints to world axis
- showing or hiding local rotation axes
- manual joint orientation tweaks

---

## Recommended Artist Usage

### Quick Object Aim Setup

1. Create or select your Aim object
2. Create or select your World Up object
3. Select the object you want to orient
4. Choose Aim and Up axis in the UI
5. Enable **REMOVE_CONSTRAINT** if you only want a one-time orientation result
6. Click **Orient Selection**

---

### Surface Locator Setup

1. Select a face, edge, or vertex on a mesh
2. Click **ORIENT** to create an orient locator
3. Select or create Aim and World Up locators
4. Use the three-object selection workflow to orient your locator or helper object

---

### Suggested Selection Naming

The tool automatically builds locator names from the selected object name:

```text
sourceObject_aimUp
sourceObject_orient
sourceObject_worldUp
```

For namespaced assets, the namespace is preserved where possible.

---

## Important Notes

- Do not mix selection types when creating locators. Select only objects, vertices, edges, or faces.
- For the Orient Selection workflow, selection order matters.
- Aim Axis and Up Axis should not be the same direction.
- If a locator already exists for `aimUp` or `worldUp`, delete the old one before creating a new one.
- `orient` locator creation allows numbered duplicates for repeated testing.
- Always inspect the final result before using it in a rig or animation publish.

---

## Installation

1. Place the tool folder inside your Maya scripts/tool directory.
2. Make sure the main UI file is available to Maya, for example:

```text
OrientAimUp_UI.py
```

3. If using the bundled JAMMSoft menu item, keep the JAMMSoft script in the expected folder structure:

```text
01_Script/jammOrientJoint.py
```

4. Launch the UI from your shelf button or Python command.

Example Python launch command:

```python
import OrientAimUp_UI
OrientAimUp_UI.OrientAimUp_UI()
```

For a reload-safe shelf command, use your studio's standard safe reload wrapper if required.

---

## Credits & Reference

### OrientAimUp Tool

- Tool integration / UI workflow: **Lui Kit Fai (RIGGER)**
- Developed for Maya orientation helper workflows under the **GLOW PRODUCTION** tool style

### JAMMSoft Joint Orient Tool

The bundled joint orientation script is credited to:

- **Jose Antonio Martin Martin**
- Email: `JoseAntonioMartinMartin@gmail.com`
- Email: `contact@joseantoniomartinmartin.com`
- Website: `http://www.joseantoniomartinmartin.com`
- Copyright 2010 Jose Antonio Martin Martin — All Rights Reserved

All credit for the JAMMSoft Joint Orient Tool belongs to the original author.

---

## Feedback & Contributions

This is an evolving internal Maya helper tool.

Feedback, production issues, and improvement ideas are welcome, especially around:

- locator placement behaviour
- component-selection orientation
- artist-facing naming rules
- automation mode design
- safer rigging workflows

---

## License

Provided **as-is** for personal, internal production, and educational use.

The bundled JAMMSoft Joint Orient Tool keeps its original author credit and copyright notice.
