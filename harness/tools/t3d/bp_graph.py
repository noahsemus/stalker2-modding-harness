"""Graph builder on top of bp_t3d: declare nodes and pins, link(a, b), emit paste text.

Links are written on both ends, so the pasted graph never depends on one-sided LinkedTo.
"""
from bp_t3d import G, head, comment_box, T, F, TGT


class Pin:
    def __init__(self, node, name, cat, sub="None", subcat="", out=False, hidden=False, adv=False, extra=""):
        self.node, self.name, self.cat, self.sub, self.subcat = node, name, cat, sub, subcat
        self.out, self.hidden, self.adv, self.extra, self.id, self.links = out, hidden, adv, extra, G(), []
        self.member_ref = ""   # e.g. MemberParent=...,MemberName="ReceiveTick" for an event's OutputDelegate
        self.container = "None"  # "Array" for array pins
        self.wrapper = False     # TSubclassOf function parameters
        self.ref = False         # by-reference parameter
        self.const = False

    def text(self):
        l = ("LinkedTo=(" + "".join(f"{p.node.name} {p.id}," for p in self.links) + "),") if self.links else ""
        d = 'Direction="EGPD_Output",' if self.out else ""
        return (f'   CustomProperties Pin (PinId={self.id},PinName="{self.name}",{self.extra}{d}'
                f'PinType.PinCategory="{self.cat}",PinType.PinSubCategory="{self.subcat}",'
                f'PinType.PinSubCategoryObject={self.sub},'
                + T.replace("PinType.PinSubCategoryMemberReference=()",
                            f"PinType.PinSubCategoryMemberReference=({self.member_ref})")
                   .replace("PinType.ContainerType=None", f"PinType.ContainerType={self.container}")
                   .replace("PinType.bIsUObjectWrapper=False", f"PinType.bIsUObjectWrapper={self.wrapper}")
                   .replace("PinType.bIsReference=False", f"PinType.bIsReference={self.ref}")
                   .replace("PinType.bIsConst=False", f"PinType.bIsConst={self.const}") + l
                + F % ("True" if self.hidden else "False", "True" if self.adv else "False"))


class Node:
    def __init__(self, graph, klass, name, x, y, comment="", body=()):
        self.klass, self.name, self.x, self.y, self.comment, self.body = klass, name, x, y, comment, list(body)
        self.pins = {}
        graph.nodes.append(self)

    def pin(self, name, cat, **kw):
        p = Pin(self, name, cat, **kw)
        self.pins[name] = p
        return p

    def __getitem__(self, name):
        return self.pins[name]

    def text(self):
        return head(self.klass, self.name, self.x, self.y, self.comment, self.body) + \
            [p.text() for p in self.pins.values()] + ["End Object"]


class Graph:
    def __init__(self):
        self.nodes, self.extra, self.boxes = [], [], []
        # untangle() clones a shared pure node once per consumer, and with it its whole input tree; deep shared trees
        # (a camera basis feeding dozens of pins) multiply into thousands of nodes and an editor that runs out of
        # memory deleting them. A number here = only pure nodes whose upstream pure tree has at most that many nodes
        # are cloned; bigger shared trees stay one instance with several wires out. None = clone everything (old).
        self.untangle_limit = None

    def link(self, a, b):
        a.links.append(b)
        b.links.append(a)

    def box(self, name, x, y, w, h, text):
        self.boxes.append([name, x, y, w, h, text])

    def text(self):
        out = list(self.extra)
        for b in self.boxes:
            out += comment_box(*b)
        for n in self.nodes:
            out += n.text()
        return out

    # ---- readable layout -------------------------------------------------------------------------------------
    @staticmethod
    def _size(n):
        """Conservative on-screen size of a node (the editor does not export it): one ~30 px row per visible pin on the
        longer side (the exec pins share the header row), ~7.5 px per character of the widest input + output label,
        room for default-value boxes, and the comment bubble above the node (as wide as its text)."""
        import re as _re
        vis = [p for p in n.pins.values() if not p.hidden and not (p.adv and not p.links)]
        ins = [p for p in vis if not p.out and p.cat != "exec"]
        outs = [p for p in vis if p.out and p.cat != "exec"]
        execs = any(p.cat == "exec" for p in vis)
        label = lambda p: len(_re.sub(r"(?<!^)([A-Z])", r" \1", p.name))   # CamelCase -> "Camel Case"
        win = max([label(p) + (12 if ("DefaultValue" in p.extra and not p.links) else 0) for p in ins] + [0])
        wout = max([label(p) for p in outs] + [0])
        title = 0
        for b in n.body:
            m = _re.search(r'MemberName="([^"]+)"', b)
            if m:
                title = len(_re.sub(r"(?<!^)([A-Z])", r" \1", m.group(1)))
        w = max(160, int(7.5 * max(title + 6, win + wout + 6)) + 40)
        rows = max(len(ins), len(outs)) + (1 if execs else 0)
        h = 44 + 30 * max(rows, 1)
        if n.comment:
            w = max(w, int(7 * len(n.comment)) + 40)
            h += 40
        return w, h

    def layout(self, col_gap=110, row_gap=46, box_gap=260, pad=80):
        """Re-place every node so nothing overlaps and execution flows left to right.

        Each node belongs to the comment box that contained its original position (the smallest one), or to a
        trailing "rest" group. Inside a group, a node's column is its longest-path depth over the links inside the
        group (data producers to the left of their consumers, exec chains left to right); nodes in a column are
        ordered by the average row of what feeds them. Groups are stacked top to bottom in their original order and
        each box is resized to enclose its nodes."""
        def contains(b, n):
            return b[1] <= n.x <= b[1] + b[3] and b[2] <= n.y <= b[2] + b[4]

        groups = {i: [] for i in range(len(self.boxes))}
        home = {}
        for n in self.nodes:
            inside = [i for i, b in enumerate(self.boxes) if contains(b, n)]
            if inside:
                home[id(n)] = min(inside, key=lambda i: self.boxes[i][3] * self.boxes[i][4])
        for _ in range(8):   # a node outside every box joins the box of a node it is linked to
            for n in self.nodes:
                if id(n) in home:
                    continue
                for p in n.pins.values():
                    hit = [home[id(q.node)] for q in p.links if id(q.node) in home]
                    if hit:
                        home[id(n)] = hit[0]
                        break
        rest = []
        for n in self.nodes:
            (groups[home[id(n)]] if id(n) in home else rest).append(n)
        order = sorted(groups, key=lambda i: (self.boxes[i][2], self.boxes[i][1]))
        y_cursor = min([b[2] for b in self.boxes] + [0])
        x0 = min([b[1] for b in self.boxes] + [0])
        for gi in order + [None]:
            members = groups[gi] if gi is not None else rest
            if not members:
                continue
            ids = set(id(n) for n in members)
            preds = {id(n): [] for n in members}
            for n in members:
                for p in n.pins.values():
                    if p.out:
                        for q in p.links:
                            if id(q.node) in ids and q.node is not n:
                                preds[id(q.node)].append(n)
            depth = {id(n): 0 for n in members}
            for _ in range(len(members)):
                changed = False
                for n in members:
                    for m in preds[id(n)]:
                        if depth[id(m)] + 1 > depth[id(n)] and depth[id(m)] + 1 < len(members):
                            depth[id(n)] = depth[id(m)] + 1
                            changed = True
                if not changed:
                    break
            cols = {}
            for n in members:
                cols.setdefault(depth[id(n)], []).append(n)
            top = y_cursor + pad + 40
            x = x0 + pad
            bottom = top
            row_of = {}
            for c in sorted(cols):
                col = cols[c]
                col.sort(key=lambda n: (sum(row_of.get(id(m), n.y) for m in preds[id(n)]) / len(preds[id(n)])) if preds[id(n)] else n.y)
                width = max(self._size(n)[0] for n in col)
                y = top
                for n in col:
                    w, h = self._size(n)
                    n.x, n.y = int(x), int(y + (40 if n.comment else 0))
                    row_of[id(n)] = y
                    y += h + row_gap
                bottom = max(bottom, y)
                x += width + col_gap
            if gi is not None:
                b = self.boxes[gi]
                b[1], b[2], b[3], b[4] = int(x0), int(y_cursor), int(x - x0 + pad), int(bottom - y_cursor + pad)
            y_cursor = bottom + pad + box_gap

    # ---- readable layout, v2: exec rows with local data trees ---------------------------------------------------
    @staticmethod
    def _is_exec(n):
        return any(p.cat == "exec" for p in n.pins.values())

    def _clone(self, n, counter):
        """Copy of a pure node with fresh pin ids; input links are duplicated (the producers gain a link), output
        links are not copied (the caller moves one consumer link over)."""
        c = Node(self, n.klass, n.name.rsplit("_", 1)[0] + f"_{counter}", n.x, n.y, n.comment, n.body)
        for name, p in n.pins.items():
            q = c.pin(name, p.cat, sub=p.sub, subcat=p.subcat, out=p.out, hidden=p.hidden, adv=p.adv, extra=p.extra)
            q.member_ref, q.container, q.wrapper, q.ref, q.const = p.member_ref, p.container, p.wrapper, p.ref, p.const
            if not p.out:
                for src in list(p.links):
                    self.link(src, q)
        return c

    def untangle(self):
        """Give every pure node exactly one consumer link by cloning it (pure nodes are re-evaluated per use anyway),
        so data inputs can sit right next to the node that uses them instead of sending wires across the graph."""
        counter = 60000
        changed = True

        def tree_size(n, seen):
            for p in n.pins.values():
                if p.out:
                    continue
                for q in p.links:
                    m = q.node
                    if m not in seen and not self._is_exec(m):
                        seen.add(m)
                        tree_size(m, seen)
            return len(seen)

        while changed:
            changed = False
            for n in list(self.nodes):
                if self._is_exec(n):
                    continue
                if self.untangle_limit is not None and tree_size(n, set()) > self.untangle_limit:
                    continue
                uses = [(p, q) for p in n.pins.values() if p.out for q in p.links]
                for p, q in uses[1:]:
                    counter += 1
                    c = self._clone(n, counter)
                    p.links.remove(q)
                    q.links.remove(p)
                    self.link(c.pins[p.name], q)
                    changed = True

    def layout_tree(self, col_gap=90, row_gap=60, box_gap=160, pad=100, max_row=7000):
        """Readable layout. Inside each comment box the exec chain runs left to right on a row, every exec node's data
        inputs form a small tree directly to its left (untangle() first: each pure node feeds one pin), and extra exec
        outputs (Branch false, Sequence then_1..) open rows below; a chain longer than max_row wraps onto a new row.
        The boxes themselves follow the flow: a box entered
        from another box sits to the right of it, boxes fed by the same box are stacked in the order of the pins that
        feed them, and boxes nobody feeds (events) start new trees below."""
        self.untangle()

        def contains(b, n):
            return b[1] <= n.x <= b[1] + b[3] and b[2] <= n.y <= b[2] + b[4]

        def exec_out(n):
            return [q.node for p in n.pins.values() if p.cat == "exec" and p.out for q in p.links]

        def exec_in(n):
            return [q.node for p in n.pins.values() if p.cat == "exec" and not p.out for q in p.links]

        execs = [n for n in self.nodes if self._is_exec(n)]
        home = {}
        for n in execs:
            inside = [i for i, b in enumerate(self.boxes) if contains(b, n)]
            if inside:
                home[id(n)] = min(inside, key=lambda i: self.boxes[i][3] * self.boxes[i][4])
        for _ in range(12):   # an exec node outside every box joins the box it leads into, else the one it comes from
            for n in execs:
                if id(n) in home:
                    continue
                for cand in (exec_out(n), exec_in(n)):
                    hit = [home[id(m)] for m in cand if id(m) in home]
                    if hit:
                        home[id(n)] = hit[0]
                        break
        if any(id(n) not in home for n in execs):
            self.boxes.append(["EdGraphNode_Comment_999", 0, 0, 10, 10, "Other"])
            for n in execs:
                home.setdefault(id(n), len(self.boxes) - 1)
        groups = {}
        for n in execs:
            groups.setdefault(home[id(n)], []).append(n)

        def data_children(n):
            out = []
            for p in n.pins.values():
                if not p.out and p.cat != "exec":
                    for q in p.links:
                        if not self._is_exec(q.node) and q.node not in out:
                            out.append(q.node)
            return out

        placed, owner = set(), {}

        def tree_width(n):
            best = 0
            for c in data_children(n):
                best = max(best, self._size(c)[0] + col_gap // 2 + tree_width(c))
            return best

        def place_tree(n, right, top, gi):
            y = top
            for c in data_children(n):
                if id(c) in placed:
                    continue
                w, h = self._size(c)
                placed.add(id(c))
                owner[id(c)] = gi
                sub_bottom = place_tree(c, right - w - col_gap // 2, y, gi)
                c.x, c.y = int(right - w), int(y + (40 if c.comment else 0))
                y = max(y + h, sub_bottom) + row_gap // 2
            return y

        # 1. each box laid out on its own, at the origin
        extent = {}
        for gi, members in groups.items():
            ids = set(id(n) for n in members)
            entered = [n for n in members if not any(id(m) in ids for m in exec_in(n))] or members[:1]
            entered.sort(key=lambda n: (n.y, n.x))
            state = {"bottom": 0, "right": 0}

            def run(n, x, top):
                if id(n) in placed or id(n) not in ids:
                    return
                placed.add(id(n))
                owner[id(n)] = gi
                tw = tree_width(n)
                w, h = self._size(n)
                nx = x + tw
                n.x, n.y = int(nx), int(top + (40 if n.comment else 0))
                tb = place_tree(n, nx - col_gap // 2, top, gi) if tw else top
                state["bottom"] = max(state["bottom"], top + h + 40, tb)
                state["right"] = max(state["right"], nx + w)
                first = True
                for m in exec_out(n):
                    if id(m) in placed or id(m) not in ids:
                        continue
                    if first:
                        if nx + w + col_gap > max_row:      # wrap a long chain onto a new row, like a line of text
                            run(m, 0, state["bottom"] + row_gap)
                        else:
                            run(m, nx + w + col_gap, top)
                        first = False
                    else:                                   # extra outputs open a row below (wrapped too: a long
                        run(m, 0 if nx + w + col_gap > max_row else nx + w + col_gap, state["bottom"] + row_gap)   # else-chain)

            for k, r in enumerate(entered):
                run(r, 0, 0 if k == 0 else state["bottom"] + row_gap)
            extent[gi] = (state["right"], state["bottom"])

        # 2. boxes as a flow tree: box B is a child of the first box (breadth-first from the roots) with an exec link
        # into B. Roots are the boxes holding an event (an exec node with no exec input); a box still unreached
        # becomes a root too. (Marking "fed" greedily lost every root when two boxes link both ways: nothing was
        # placed, the boxes kept their generator sizes and most nodes ended up outside them.)
        links = {gi: [] for gi in groups}
        for gi, members in groups.items():
            for n in sorted(members, key=lambda n: (n.y, n.x)):
                for m in exec_out(n):
                    gj = home.get(id(m))
                    if gj is not None and gj != gi and gj not in links[gi]:
                        links[gi].append(gj)
        has_event = set(gi for gi, members in groups.items() if any(not exec_in(n) for n in members))
        order = sorted(groups, key=lambda gi: (gi not in has_event, self.boxes[gi][2], self.boxes[gi][1]))
        feeds = {gi: [] for gi in groups}
        reached, roots = set(), []
        for r in order:
            if r in reached:
                continue
            roots.append(r)
            reached.add(r)
            queue = [r]
            while queue:
                a = queue.pop(0)
                for b in links[a]:
                    if b not in reached:
                        reached.add(b)
                        feeds[a].append(b)
                        queue.append(b)
        origin = {}

        def place_box(gi, x, y):
            """Place box gi with its top-left at (x, y) and its fed boxes to its right; returns the subtree bottom."""
            w, h = extent[gi][0] + 2 * pad, extent[gi][1] + 2 * pad + 40
            origin[gi] = (x, y, w, h)
            child_y = y
            for gj in feeds[gi]:
                child_y = place_box(gj, x + w + box_gap, child_y) + box_gap
            return max(y + h, child_y - box_gap)

        y = min([b[2] for b in self.boxes] + [0])
        x0 = min([b[1] for b in self.boxes] + [0])
        for gi in roots:
            y = place_box(gi, x0, y) + box_gap * 2
        # 3. move every node with its box; resize the boxes
        for n in self.nodes:
            gi = owner.get(id(n))
            if gi is None or gi not in origin:
                continue
            bx, by, _, _ = origin[gi]
            n.x, n.y = int(n.x + bx + pad), int(n.y + by + pad + 40)
        for gi, (bx, by, w, h) in origin.items():
            b = self.boxes[gi]
            b[1], b[2], b[3], b[4] = int(bx), int(by), int(w), int(h)

    # ---- pages: one Blueprint graph split over several event graph pages ----------------------------------------
    def paginate(self, roots, default, prefix, self_class):
        """Split the graph over event graph pages so each paste (and each delete in the editor) stays small; a build
        then only re-pastes the pages whose text changed (page_digest). roots = [(page, [exec nodes])] in priority
        order: an exec node belongs to the first page whose start nodes reach it along exec links, else to default.
        Every exec link that crosses pages becomes a call on the source page (K2Node_CallFunction, self) to a custom
        event on the target page (one per target node; calls run synchronously, so execution order is unchanged).
        A pure node needed on several pages is cloned onto each, with its pure input tree. A data link from an exec
        node's output to another page cannot be split: it raises (keep both ends on one page, or pass the value
        through a variable). Pure nodes nobody reads are dropped. Comment boxes go to the page holding most of their exec nodes.
        Returns {page: Graph} in the order of roots (default first)."""
        from bp_t3d import TGT as _TGT
        is_exec = self._is_exec
        page = {}
        for pg, starts in roots:
            stack = list(starts)
            while stack:
                n = stack.pop()
                if id(n) in page:
                    continue
                page[id(n)] = pg
                for p in n.pins.values():
                    if p.out and p.cat == "exec":
                        stack += [q.node for q in p.links]
        for n in self.nodes:
            if is_exec(n):
                page.setdefault(id(n), default)
        need = {}

        def needed(n, path=()):
            if is_exec(n):
                return {page[id(n)]}
            if id(n) in need:
                return need[id(n)]
            s = set()
            for p in n.pins.values():
                if p.out:
                    for q in p.links:
                        if id(q.node) not in path:
                            s |= needed(q.node, path + (id(n),))
            need[id(n)] = s   # empty: a pure node nobody reads (dropped from every page)
            return need[id(n)]
        for n in self.nodes:
            needed(n)
        order = [default] + [pg for pg, _ in roots if pg != default]
        pages = {pg: Graph() for pg in order}
        for pg in pages.values():
            pg.untangle_limit = self.untangle_limit
        # every node's instance on each page it is needed on: the original on its first page, clones elsewhere
        inst = {}
        counter = [100000]
        for n in list(self.nodes):
            pgs = sorted(needed(n), key=order.index)
            for k, pg in enumerate(pgs):
                if k == 0:
                    c = n
                else:
                    counter[0] += 1
                    c = Node(pages[pg], n.klass, n.name.rsplit("_", 1)[0] + f"_{counter[0]}", n.x, n.y, n.comment, n.body)
                    pages[pg].nodes.pop()   # appended below with the originals, in creation order
                    for name, p in n.pins.items():
                        q = c.pin(name, p.cat, sub=p.sub, subcat=p.subcat, out=p.out, hidden=p.hidden, adv=p.adv, extra=p.extra)
                        q.member_ref, q.container, q.wrapper, q.ref, q.const = p.member_ref, p.container, p.wrapper, p.ref, p.const
                inst[(id(n), pg)] = c
        # rebuild the links page by page
        links = [(p, q) for n in self.nodes for p in n.pins.values() if p.out for q in list(p.links)]
        for n in self.nodes:
            for p in n.pins.values():
                p.links = []
        events = {}
        for p, q in links:
            a, b = p.node, q.node
            if p.cat == "exec":
                pa, pb = page[id(a)], page[id(b)]
                if pa == pb:
                    self.link(p, q)
                    continue
                key = (id(b), q.name)
                if key not in events:
                    ename = f"{prefix}{pb.replace(' ', '')}_{len([1 for k in events if events[k][1] == pb])}"
                    ev = Node(pages[pb], "/Script/BlueprintGraph.K2Node_CustomEvent", f"K2Node_CustomEvent_{counter[0] + 1}",
                              b.x - 400, b.y - 150, f"from page {pa}", [f'CustomFunctionName="{ename}"'])
                    counter[0] += 1
                    pages[pb].nodes.pop()
                    od = ev.pin("OutputDelegate", "delegate", out=True)
                    od.member_ref = f'MemberName="{ename}",bSelfContext=True'
                    ev.pin("then", "exec", out=True)
                    self.link(ev.pins["then"], q)
                    events[key] = (ev, pb, ename)
                ev, _, ename = events[key]
                counter[0] += 1
                call = Node(pages[pa], "/Script/BlueprintGraph.K2Node_CallFunction", f"K2Node_CallFunction_{counter[0]}",
                            a.x + 300, a.y, f"to page {pb}", [f'FunctionReference=(MemberName="{ename}",bSelfContext=True)'])
                pages[pa].nodes.pop()
                call.pin("execute", "exec")
                call.pin("then", "exec", out=True)
                call.pin("self", "object", sub=self_class, extra=_TGT)
                self.link(p, call.pins["execute"])
                inst[("call", id(call))] = call
                inst[("ev", id(ev))] = ev
                page[id(call)], page[id(ev)] = pa, pb
                continue
            for pg in needed(b):
                src = inst.get((id(a), pg))
                if src is None:
                    raise ValueError(f"data link {a.name}.{p.name} -> {b.name}.{q.name} crosses from page {page.get(id(a))} to {pg}")
                self.link(src.pins[p.name], inst[(id(b), pg)].pins[q.name])
        # nodes per page, in creation order (originals, then their clones, then events and calls)
        for key, c in inst.items():
            pg = page[id(c)] if key[0] in ("call", "ev") else key[1]
            if c not in pages[pg].nodes:
                pages[pg].nodes.append(c)
        for b in self.boxes:
            inside = [page[id(n)] for n in self.nodes if is_exec(n) and b[1] <= n.x <= b[1] + b[3] and b[2] <= n.y <= b[2] + b[4]]
            if inside:
                pages[max(set(inside), key=inside.count)].boxes.append(b)
        return pages


def page_digest(lines):
    """Hash of a page's paste text without the per-build noise (node names, pin ids, GUIDs), so a build reports only
    the pages whose content really changed (positions and comment box sizes ignored)."""
    import hashlib, re as _re
    text = "\n".join(lines)
    names = {}
    for m in _re.finditer(r'Name="([A-Za-z0-9_]+_\d+)"', text):
        names.setdefault(m.group(1), f"N{len(names)}")
    text = _re.sub(r"\b(" + "|".join(map(_re.escape, names)) + r")\b", lambda m: names[m.group(1)], text) if names else text
    text = _re.sub(r"(PinId|NodeGuid|PersistentGuid)=[0-9A-F]{32}", r"\1=X", text)
    text = _re.sub(r" [0-9A-F]{32},", " X,", text)
    text = _re.sub(r"\n\s*Node(PosX|PosY|Width|Height)=-?\d+", "", text)   # layout only: no re-paste for a moved node or box
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
